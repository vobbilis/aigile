import { LineChart, Line, ResponsiveContainer } from 'recharts'

interface SparklineChartProps {
  data: { value: number }[]
  width?: number
  height?: number
}

export function SparklineChart({ data, height = 60 }: SparklineChartProps) {
  if (data.length === 0) {
    return null
  }

  const chartData = data.length === 1 ? [data[0], data[0]] : data

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="value"
          stroke="#8884d8"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
