import { useCallback, useEffect, useRef, useState } from 'react'
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
  const [healthError, setHealthError] = useState(null)
  const [events, setEvents] = useState([])
  const seqRef = useRef(0)

  // One socket for the whole app. Events are buffered with a sequence number
  // so batched React updates cannot silently drop any of them.
  const handleEvent = useCallback((event) => {
    seqRef.current += 1
    setEvents((prev) => [...prev.slice(-199), { ...event, _seq: seqRef.current }])
  }, [])
  const { connected } = useWebSocket(handleEvent)

  useEffect(() => {
    api
      .health()
      .then((result) => {
        setHealth(result)
        setHealthError(null)
      })
      // Surface this instead of silently rendering defaults - a swallowed
      // error here looks exactly like "everything is in mock mode".
      .catch((error) => {
        setHealth(null)
        setHealthError(error.message || 'Could not reach the backend')
      })
  }, [])

  return (
    <Layout connected={connected} health={health} healthError={healthError}>
      <Routes>
        <Route path="/" element={<Dashboard events={events} />} />
        <Route path="/demo" element={<DemoCall events={events} health={health} />} />
        <Route path="/leads" element={<Leads />} />
        <Route path="/leads/:id" element={<LeadDetail />} />
        <Route path="/calls" element={<Calls />} />
        <Route path="/callbacks" element={<Callbacks events={events} />} />
        <Route path="/training" element={<Training />} />
        <Route path="/settings" element={<Settings health={health} onHealth={setHealth} />} />
      </Routes>
    </Layout>
  )
}
