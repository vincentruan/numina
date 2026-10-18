export interface OSSComponent {
  name: string
  license: string
  url: string
}

export const ossComponents: OSSComponent[] = [
  { name: 'Vue 3', license: 'MIT', url: 'https://vuejs.org' },
  { name: 'Vant 4', license: 'MIT', url: 'https://vant-ui.github.io/vant' },
  { name: 'FastAPI', license: 'MIT', url: 'https://fastapi.tiangolo.com' },
  { name: 'SQLAlchemy', license: 'MIT', url: 'https://www.sqlalchemy.org' },
  { name: 'DeerFlow', license: 'MIT', url: 'https://github.com/bytedance/deer-flow' },
  { name: 'LangChain', license: 'MIT', url: 'https://www.langchain.com' },
  { name: 'LangGraph', license: 'MIT', url: 'https://github.com/langchain-ai/langgraph' },
  { name: 'ECharts', license: 'Apache-2.0', url: 'https://echarts.apache.org' },
  { name: 'DuckDB', license: 'MIT', url: 'https://duckdb.org' },
  { name: 'Vite', license: 'MIT', url: 'https://vitejs.dev' },
  { name: 'Pinia', license: 'MIT', url: 'https://pinia.vuejs.org' },
  { name: 'vue-i18n', license: 'MIT', url: 'https://vue-i18n.intlify.dev' },
  { name: 'Tavily', license: 'MIT', url: 'https://tavily.com' },
  { name: 'e2b', license: 'Apache-2.0', url: 'https://e2b.dev' },
]
