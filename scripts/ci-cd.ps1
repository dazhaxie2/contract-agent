# =====================================================================
# 本机 Docker Desktop K8s 按需 CI/CD - PowerShell 入口
# ---------------------------------------------------------------------
# 用法（举例）:
#   .\scripts\ci-cd.ps1 all                          # 完整链路
#   .\scripts\ci-cd.ps1 auto                         # 看 git diff 智能选阶段+组件
#   .\scripts\ci-cd.ps1 ci                           # lint + test
#   .\scripts\ci-cd.ps1 cd                           # build + deploy + verify
#   .\scripts\ci-cd.ps1 build deploy                 # 任意组合
#   .\scripts\ci-cd.ps1 watch                        # 文件变化触发 fast 链路
#   .\scripts\ci-cd.ps1 -Component backend all       # 只跑 backend
#   .\scripts\ci-cd.ps1 -SkipTest -NoCache all       # 跳过 test、不用 docker 缓存
#   .\scripts\ci-cd.ps1 -DryRun all                  # 只打印不执行
#
# 阶段 (Stages):
#   lint          backend ruff + frontend eslint
#   test          backend pytest（前端没配 test，先跳过）
#   build         docker build backend/frontend -> :latest + :<git-sha>
#   deploy        kubectl 应用到本机 docker-desktop K8s，按 sha tag 触发 rollout
#   verify        等 rollout 完成 + /health 冒烟
#
# 别名 (Aliases):
#   ci   = lint, test
#   cd   = build, deploy, verify
#   all  = lint, test, build, deploy, verify
#   fast = lint, build, deploy, verify        （省 test，开发循环最快）
#   auto = 看 git diff --name-only 决定要跑哪些组件 + 阶段
# =====================================================================

[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]] $Stages = @('all'),

    # 限定组件：backend / frontend / both（默认 both）
    [ValidateSet('backend', 'frontend', 'both')]
    [string[]] $Component = @('both'),

    [switch] $SkipTest,
    [switch] $SkipLint,
    [switch] $NoCache,
    [switch] $DryRun,
    [switch] $KeepGoing,           # 出错继续后续阶段（默认：fail-fast）
    [string] $Context = 'docker-desktop',
    [string] $Namespace = 'contract-agent',
    [int]    $RolloutTimeoutSec = 300
)

$ErrorActionPreference = 'Stop'
$script:RepoRoot       = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:StartTime      = Get-Date
$script:StageResults   = [System.Collections.Generic.List[object]]::new()

# --------------------------- 日志辅助 ----------------------------------
function _ts { (Get-Date).ToString('HH:mm:ss') }
function Info  ($msg) { Write-Host "[$(_ts)] $msg" -ForegroundColor Cyan }
function Ok    ($msg) { Write-Host "[$(_ts)] OK  $msg" -ForegroundColor Green }
function Warn  ($msg) { Write-Host "[$(_ts)] WRN $msg" -ForegroundColor Yellow }
function Fail  ($msg) { Write-Host "[$(_ts)] ERR $msg" -ForegroundColor Red }
function Step  ($msg) { Write-Host ""; Write-Host "==> [$(_ts)] $msg" -ForegroundColor Magenta }

$script:LastCmdExit = 0
function Invoke-Cmd {
    [CmdletBinding()]
    param([string]$Cmd, [string]$Cwd = $script:RepoRoot, [switch]$IgnoreError)
    if ($DryRun) {
        Write-Host "[$(_ts)] DRY $Cmd" -ForegroundColor DarkGray
        $script:LastCmdExit = 0
        return
    }
    Write-Host "[$(_ts)] >>> $Cmd" -ForegroundColor DarkGray
    $prev = Get-Location
    try {
        Set-Location $Cwd
        # cmd /c 让 stderr 进入正常输出流，避免 5.1 把它当 ErrorRecord
        & cmd /c "$Cmd 2>&1"
        $code = $LASTEXITCODE
        $script:LastCmdExit = $code
        if ($code -ne 0 -and -not $IgnoreError) {
            throw "命令失败 (exit=$code): $Cmd"
        }
    } finally {
        Set-Location $prev
    }
}

# --------------------------- 通用预检 ----------------------------------
function Test-Tool($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Assert-Prereqs($needK8s) {
    Step "环境预检"
    if (-not (Test-Tool 'docker')) { throw "找不到 docker。请先启动 Docker Desktop。" }
    # 预检不参与 -DryRun，永远真实执行
    # 注：5.1 把 native 命令的 stderr 行包装成 ErrorRecord，配合 $ErrorActionPreference='Stop' 会触发异常。
    # 用 cmd /c "... > nul 2>&1" 让 cmd 自己吞掉，PowerShell stream 完全干净。
    & cmd /c "docker info > nul 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "docker daemon 未就绪，请确认 Docker Desktop 已启动。" }
    Ok "docker daemon 可用"

    if ($needK8s) {
        if (-not (Test-Tool 'kubectl')) { throw "找不到 kubectl。" }
        & cmd /c "kubectl --context $Context cluster-info > nul 2>&1"
        if ($LASTEXITCODE -ne 0) {
            if ($DryRun) {
                Warn "kubectl 连不上 context=$Context（DryRun 不阻断）"
            } else {
                throw "kubectl 连不上 context=$Context。请在 Docker Desktop 启用 Kubernetes。"
            }
        } else {
            Ok "kubectl context=$Context 可用"
        }
    }
}

# --- native 命令辅助：避开 5.1 的 NativeCommandError 陷阱 ---
function Test-NativeCmd([string]$Cmd) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & cmd /c "$Cmd > nul 2>&1"
        return ($LASTEXITCODE -eq 0)
    } finally { $ErrorActionPreference = $prev }
}
function Get-NativeOutput([string]$Cmd) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        return (& cmd /c "$Cmd 2>nul")
    } finally { $ErrorActionPreference = $prev }
}

function Get-GitSha {
    $sha = Get-NativeOutput "git -C `"$($script:RepoRoot)`" rev-parse --short=12 HEAD"
    if (-not $sha) { $sha = (Get-Date).ToString('yyyyMMddHHmmss') }
    return $sha.Trim()
}

function Get-ChangedFiles {
    # 与上游 origin/main 比较；没有 remote 时退而求其次比 HEAD~1；都没有就只看 working tree
    $base = $null
    if (Test-NativeCmd "git -C `"$($script:RepoRoot)`" rev-parse --verify origin/main") {
        $base = 'origin/main...HEAD'
    } elseif (Test-NativeCmd "git -C `"$($script:RepoRoot)`" rev-parse --verify HEAD~1") {
        $base = 'HEAD~1'
    }

    $tracked = @()
    if ($base) {
        $tracked = (Get-NativeOutput "git -C `"$($script:RepoRoot)`" diff --name-only $base") -split "`n"
    }
    $unstaged  = (Get-NativeOutput "git -C `"$($script:RepoRoot)`" diff --name-only") -split "`n"
    $untracked = (Get-NativeOutput "git -C `"$($script:RepoRoot)`" ls-files --others --exclude-standard") -split "`n"

    return @($tracked + $unstaged + $untracked) | Where-Object { $_ } | Select-Object -Unique
}

function Resolve-AutoSelection {
    $files = @(Get-ChangedFiles)
    if ($files.Count -eq 0) {
        Info "git diff 没看到变化，按 ci 处理（lint+test）"
        return @{ Stages = @('lint', 'test'); Components = @('both') }
    }

    $touchBackend  = $files | Where-Object { $_ -match '^backend/' }
    $touchFrontend = $files | Where-Object { $_ -match '^frontend/' }
    $touchK8s      = $files | Where-Object { $_ -match '^(k8s|helm)/' -or $_ -eq 'docker-compose.yml' }

    $components = @()
    if ($touchBackend)  { $components += 'backend' }
    if ($touchFrontend) { $components += 'frontend' }
    if (-not $components) { $components = @('both') }

    # 阶段：app 代码变动 → 全链路；只动 manifest → 跳过 lint/test 直接 deploy/verify
    $stages = @()
    if ($touchBackend -or $touchFrontend) {
        $stages = @('lint', 'test', 'build', 'deploy', 'verify')
    } elseif ($touchK8s) {
        $stages = @('deploy', 'verify')
    } else {
        $stages = @('lint')
    }

    Info ("Auto: 改动 {0} 个文件，组件={1}，阶段={2}" -f $files.Count, ($components -join ','), ($stages -join ','))
    return @{ Stages = $stages; Components = $components }
}

# --------------------------- 阶段实现 ----------------------------------
function Stage-Lint {
    Step "Lint"
    $comps = $script:ActiveComponents

    if ($comps -contains 'backend') {
        Info "backend: ruff check"
        # 没装就快速装一下（沿用 ci.yml 的做法）
        Invoke-Cmd "python -m pip install --quiet ruff" -Cwd (Join-Path $RepoRoot 'backend')
        Invoke-Cmd "python -m ruff check ." -Cwd (Join-Path $RepoRoot 'backend')
        Ok "backend ruff 通过"
    }

    if ($comps -contains 'frontend') {
        Info "frontend: npm run lint"
        # eslint 没装则 npm ci；否则直接 lint
        if (-not (Test-Path (Join-Path $RepoRoot 'frontend\node_modules'))) {
            Invoke-Cmd "npm ci" -Cwd (Join-Path $RepoRoot 'frontend')
        }
        # 前端 lint 当前未必干净 —— 与现有 ci.yml 一致，记录但不阻塞
        Invoke-Cmd "npm run lint" -Cwd (Join-Path $RepoRoot 'frontend') -IgnoreError
        if ($script:LastCmdExit -ne 0) { Warn "frontend lint 有告警 (continue-on-error，与云端 CI 一致)" }
        else { Ok "frontend lint 通过" }
    }
}

function Stage-Test {
    Step "Test"
    if ($SkipTest) { Warn "已 -SkipTest，跳过"; return }
    $comps = $script:ActiveComponents

    if ($comps -contains 'backend') {
        Info "backend: pytest（依赖 docker-compose 起 hidb+redis）"
        # 确保 test 依赖在本机起着（docker ps 不会写 stderr，避开 5.1 的 NativeCommandError 陷阱）
        $needSvcs = @('hidb', 'redis')
        foreach ($s in $needSvcs) {
            $running = & docker ps -q -f "name=contract-agent-$s" -f "status=running"
            if (-not $running) {
                Info "依赖 $s 未运行，docker compose up -d $s"
                Invoke-Cmd "docker compose up -d $s"
            }
        }
        # 直接 host 跑 pytest（用 5432/6379 端口映射），与 ci.yml services 等价
        $env:DB_PROVIDER          = 'hidb_pg'
        $env:DB_HOST              = 'localhost'
        $env:DB_PORT              = '5432'
        $env:DB_USER              = 'hidb'
        $env:DB_PASSWORD          = 'hidb123'
        $env:DB_NAME              = 'contract_agent'
        $env:DB_READ_TARGET       = 'hidb'
        $env:DB_DUAL_WRITE_ENABLED = 'false'
        $env:DB_AUTO_CREATE_SCHEMA = 'false'
        $env:REDIS_HOST           = 'localhost'
        $env:REDIS_PORT           = '6379'
        $env:ENVIRONMENT          = 'test'
        Invoke-Cmd "python -m pytest tests/ -q" -Cwd (Join-Path $RepoRoot 'backend')
        Ok "backend pytest 通过"
    }

    if ($comps -contains 'frontend') {
        Warn "frontend 当前未配置单元测试，跳过"
    }
}

function Stage-Build {
    Step "Build"
    $sha = Get-GitSha
    $script:BuildSha = $sha
    Info "镜像 tag: :latest + :$sha"

    $cacheFlag = if ($NoCache) { '--no-cache' } else { '' }

    $comps = $script:ActiveComponents
    if ($comps -contains 'backend') {
        Invoke-Cmd "docker build $cacheFlag -t contract-agent-backend:latest -t contract-agent-backend:$sha ./backend"
        Ok "backend image 构建完成 (sha=$sha)"
    }
    if ($comps -contains 'frontend') {
        Invoke-Cmd "docker build $cacheFlag -t contract-agent-frontend:latest -t contract-agent-frontend:$sha ./frontend"
        Ok "frontend image 构建完成 (sha=$sha)"
    }

    # 把 sha 落到 .ci-cd.lastbuild 便于 deploy 阶段单独触发
    Set-Content -Path (Join-Path $RepoRoot '.ci-cd.lastbuild') -Value $sha
}

function Stage-Deploy {
    Step "Deploy"
    # 没传 build sha 时，读上次 build 落下的 sha；都没有就用 git sha
    if (-not $script:BuildSha) {
        $f = Join-Path $RepoRoot '.ci-cd.lastbuild'
        if (Test-Path $f) { $script:BuildSha = (Get-Content $f).Trim() }
    }
    if (-not $script:BuildSha) { $script:BuildSha = Get-GitSha }
    $sha = $script:BuildSha

    # namespace 不存在 → 一次性 apply 整个 k8s/local/（cmd /c 吞 stderr，避开 5.1 ErrorRecord 坑）
    & cmd /c "kubectl --context $Context get ns $Namespace > nul 2>&1"
    if ($LASTEXITCODE -ne 0) {
        Info "ns=$Namespace 不存在，初始化 k8s/local 全量"
        foreach ($f in @('00-base.yaml', '10-data.yaml', '20-milvus.yaml', '30-kafka.yaml', '40-nebula.yaml', '50-app.yaml')) {
            Invoke-Cmd "kubectl --context $Context apply -f k8s/local/$f"
        }
    } else {
        # 只 apply app 层（避免改动数据层）
        Invoke-Cmd "kubectl --context $Context apply -f k8s/local/50-app.yaml"
    }

    # 用 sha tag patch 镜像，强制 K8s 重建 pod
    $comps = $script:ActiveComponents
    if ($comps -contains 'backend') {
        Invoke-Cmd "kubectl --context $Context -n $Namespace set image deploy/backend backend=contract-agent-backend:$sha"
    }
    if ($comps -contains 'frontend') {
        Invoke-Cmd "kubectl --context $Context -n $Namespace set image deploy/frontend frontend=contract-agent-frontend:$sha"
    }
    Ok "deploy 完成，镜像 tag=$sha"
}

function Stage-Verify {
    Step "Verify"
    $comps = $script:ActiveComponents

    foreach ($c in $comps) {
        Info "等 deploy/$c rollout 完成 (≤ ${RolloutTimeoutSec}s)"
        Invoke-Cmd "kubectl --context $Context -n $Namespace rollout status deploy/$c --timeout=${RolloutTimeoutSec}s"
    }

    if ($comps -contains 'backend') {
        Info "backend /health 冒烟（pod 内）"
        if ($DryRun) { Write-Host "[$(_ts)] DRY 冒烟" -ForegroundColor DarkGray; return }
        # 重试 6 次 × 5s = 30s
        $ok = $false
        for ($i = 1; $i -le 6; $i++) {
            & cmd /c "kubectl --context $Context -n $Namespace exec deploy/backend -- curl -sf http://localhost:8000/health > nul 2>&1"
            if ($LASTEXITCODE -eq 0) { $ok = $true; break }
            Start-Sleep -Seconds 5
        }
        if (-not $ok) {
            & kubectl --context $Context -n $Namespace get pods -l app.kubernetes.io/component=backend
            & kubectl --context $Context -n $Namespace logs deploy/backend --tail=80
            throw "backend /health 持续失败"
        }
        Ok "backend /health 通过"
    }
}

# --------------------------- watch 模式 --------------------------------
function Start-WatchLoop {
    Step "watch 模式：监听 backend/ frontend/ 文件变化，自动跑 fast"
    if (-not (Test-Tool 'git')) { throw "watch 需要 git" }
    $lastDigest = ''
    while ($true) {
        $digest = (Get-NativeOutput "git -C `"$RepoRoot`" status --porcelain") | Out-String
        $digest = $digest.Trim()
        if ($digest -ne '' -and $digest -ne $lastDigest) {
            $lastDigest = $digest
            Info "检测到变化，触发 fast 链路"
            try {
                & $PSCommandPath -Stages 'fast' -Component $Component -SkipTest:$SkipTest -NoCache:$NoCache -Context $Context -Namespace $Namespace
            } catch {
                Fail $_.Exception.Message
            }
            Info "等待下一次变化…  (Ctrl+C 退出)"
        }
        Start-Sleep -Seconds 3
    }
}

# --------------------------- 调度 --------------------------------------
function Expand-Stages([string[]]$stages) {
    $out = @()
    foreach ($s in $stages) {
        switch ($s.ToLowerInvariant()) {
            'all'    { $out += @('lint','test','build','deploy','verify') }
            'ci'     { $out += @('lint','test') }
            'cd'     { $out += @('build','deploy','verify') }
            'fast'   { $out += @('lint','build','deploy','verify') }
            'auto'   { $out += '__auto__' }
            'watch'  { $out += '__watch__' }
            default  { $out += $s.ToLowerInvariant() }
        }
    }
    return ,$out
}

function Run-Stage($name) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $status = 'ok'
    try {
        switch ($name) {
            'lint'   { if ($SkipLint) { Warn '已 -SkipLint，跳过'; return } Stage-Lint }
            'test'   { Stage-Test }
            'build'  { Stage-Build }
            'deploy' { Stage-Deploy }
            'verify' { Stage-Verify }
            default  { throw "未知阶段: $name" }
        }
    } catch {
        $status = 'fail'
        Fail "阶段 $name 失败: $($_.Exception.Message)"
        if (-not $KeepGoing) { throw }
    } finally {
        $sw.Stop()
        $script:StageResults.Add([pscustomobject]@{
            Stage    = $name
            Duration = [int]$sw.Elapsed.TotalSeconds
            Status   = $status
        })
    }
}

function Show-Summary {
    Write-Host ""
    Write-Host "============== CI/CD 总结 ==============" -ForegroundColor Magenta
    $script:StageResults | Format-Table Stage, Duration, Status -AutoSize | Out-String | Write-Host
    $total = [int]((Get-Date) - $script:StartTime).TotalSeconds
    $failed = ($script:StageResults | Where-Object Status -eq 'fail').Count
    if ($failed -gt 0) {
        Fail "${failed} 个阶段失败，总耗时 ${total}s"
        exit 1
    } else {
        Ok "全部阶段通过，总耗时 ${total}s（镜像 sha=$($script:BuildSha)）"
    }
}

# --------------------------- main --------------------------------------
$expanded = Expand-Stages $Stages

# 处理 auto/watch 优先级
if ($expanded -contains '__watch__') {
    Assert-Prereqs -needK8s $true
    if ($Component -contains 'both') {
        $script:ActiveComponents = @('backend','frontend')
    } else {
        $script:ActiveComponents = $Component
    }
    Start-WatchLoop
    return
}
if ($expanded -contains '__auto__') {
    $sel = Resolve-AutoSelection
    $expanded = $sel.Stages
    $Component = $sel.Components
}

# 默认 both → 展开
$script:ActiveComponents = if ($Component -contains 'both') { @('backend', 'frontend') } else { $Component }
Info ("组件: {0}" -f ($script:ActiveComponents -join ','))
Info ("阶段: {0}" -f ($expanded -join ' -> '))

# 是否需要 K8s（任一阶段是 deploy/verify）
$needK8s = ($expanded | Where-Object { $_ -in @('deploy','verify') }).Count -gt 0
Assert-Prereqs -needK8s:$needK8s

foreach ($s in $expanded) { Run-Stage $s }

Show-Summary
