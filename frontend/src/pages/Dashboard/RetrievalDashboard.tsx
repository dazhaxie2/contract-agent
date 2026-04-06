import React from 'react';
import { Card, Row, Col, Statistic, Typography, Table, Tag } from 'antd';
import { Line, Column, Pie } from '@ant-design/charts';

const { Title } = Typography;

const RetrievalDashboard: React.FC = () => {
  const recallData = [
    { k: 'Top-1', rate: 72 }, { k: 'Top-5', rate: 89 },
    { k: 'Top-10', rate: 95 }, { k: 'Top-20', rate: 98 },
  ];

  const channelData = [
    { channel: '向量检索', contribution: 55 },
    { channel: '关键词检索', contribution: 25 },
    { channel: '图谱检索', contribution: 20 },
  ];

  const rerankData = [
    { stage: '重排前', metric: 'MRR', value: 0.78 },
    { stage: '重排后', metric: 'MRR', value: 0.91 },
    { stage: '重排前', metric: 'NDCG@10', value: 0.75 },
    { stage: '重排后', metric: 'NDCG@10', value: 0.92 },
  ];

  const latencyData = [
    { stage: 'Query预处理', time: 50 },
    { stage: '向量检索', time: 80 },
    { stage: '关键词检索', time: 45 },
    { stage: '图谱检索', time: 120 },
    { stage: '融合去重', time: 10 },
    { stage: '粗排', time: 150 },
    { stage: '精排', time: 200 },
    { stage: '校验', time: 100 },
  ];

  return (
    <div>
      <Title level={4}>检索质量大盘</Title>

      <Row gutter={[16, 16]} className="mb-4">
        <Col span={6}><Card><Statistic title="Top-10 召回率" value={95} suffix="%" valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="Top-10 精确率" value={87} suffix="%" valueStyle={{ color: '#1677ff' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="MRR" value={0.91} precision={2} valueStyle={{ color: '#722ed1' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="NDCG@10" value={0.92} precision={2} valueStyle={{ color: '#faad14' }} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} className="mb-4">
        <Col span={12}>
          <Card title="Top-K 召回率" size="small">
            <Column
              data={recallData}
              xField="k"
              yField="rate"
              height={250}
              color="#1677ff"
              label={{ position: 'middle', style: { fill: '#fff' } }}
              yAxis={{ max: 100, label: { formatter: (v: string) => `${v}%` } }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="检索通道贡献占比" size="small">
            <Pie
              data={channelData}
              angleField="contribution"
              colorField="channel"
              radius={0.8}
              height={250}
              label={{ type: 'outer', content: '{name}: {percentage}' }}
              legend={{ position: 'bottom' }}
              color={['#1677ff', '#52c41a', '#722ed1']}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="重排效果对比" size="small">
            <Column
              data={rerankData}
              xField="metric"
              yField="value"
              seriesField="stage"
              isGroup
              height={250}
              color={['#d9d9d9', '#1677ff']}
              yAxis={{ max: 1.0 }}
              label={{ position: 'middle', style: { fill: '#fff' } }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="检索管线各阶段延迟(ms)" size="small">
            <Column
              data={latencyData}
              xField="stage"
              yField="time"
              height={250}
              color="#faad14"
              label={{ position: 'middle', style: { fill: '#fff' } }}
              yAxis={{ label: { formatter: (v: string) => `${v}ms` } }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default RetrievalDashboard;
