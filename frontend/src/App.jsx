import { useCallback, useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import { useWebSocket } from './hooks/useWebSocket'
import { api } from './services/api'

import Callbacks from './pages/Callbacks'
import Calls from './pages/Calls'
import Dashboard from './pages/Dashboard'
import DemoCall from './pages/DemoCall'
import LeadDetail from './pages/LeadDetail'
import Leads from './pages/Leads'
import Settings from './pages/Settings'
import Training from './pages/Training'

export default function App() {
  const [health, setHealth] = useState(null)
  const [lastEvent, setLastEvent] = useState(null)

  // One socket for the whole app; pages subscribe by reading `lastEvent`.
  const handleEvent = useCallback((event) => setLastEvent(event), [])
  const { connected } = useWebSocket(handleEvent)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  return (
    <Layout connected={connected} health={health}>
      <Routes>
        <Route path="/" element={<Dashboard lastEvent={lastEvent} />} />
        <Route path="/demo" element={<DemoCall lastEvent={lastEvent} health={health} />} />
        <Route path="/leads" element={<Leads />} />
        <Route path="/leads/:id" element={<LeadDetail />} />
        <Route path="/calls" element={<Calls />} />
        <Route path="/callbacks" element={<Callbacks lastEvent={lastEvent} />} />
        <Route path="/training" element={<Training />} />
        <Route path="/settings" element={<Settings health={health} onHealth={setHealth} />} />
      </Routes>
    </Layout>
  )
}
