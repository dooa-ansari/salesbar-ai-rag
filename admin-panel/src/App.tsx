import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import GraphEditorPage from './pages/GraphEditorPage'
import GraphsListPage from './pages/GraphsListPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<GraphsListPage />} />
        <Route path="/graphs/:id" element={<GraphEditorPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
