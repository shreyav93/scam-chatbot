import { useEffect, useRef, useState } from 'react'
import './App.css'
import DeveloperPage from "./DeveloperPage";

async function getAnswer(question) {
  const res = await fetch('/api/ask/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Request failed')
  return data
}

const LEVEL_LABELS = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
  none: 'Not rated',
}

const FACTOR_LABELS = {
  quantity: 'Independent sources used',
  relevance: 'How well sources match',
  reliability: 'How trustworthy sources are',
}

function ConfidenceSummary({ confidence }) {
  const { level, score, summary, factors, notes = [] } = confidence

  return (
    <section className={`confidence confidence-${level}`} aria-label="How well-supported this answer is">
      <h2>How well-supported is this answer?</h2>
      <p className="confidence-level">
        <strong>{LEVEL_LABELS[level] ?? level}</strong>
        {level !== 'none' && ` (${score} out of 100)`}
      </p>
      {level !== 'none' && (
        <meter min={0} max={100} low={50} high={75} optimum={100} value={score}>
          {score} out of 100
        </meter>
      )}
      <p>{summary}</p>
      <p className="confidence-caveat">
        This rates how well my sources back the answer. It does not mean the message is safe.
      </p>
      {factors && (
        <details>
          <summary>Why this score?</summary>
          <ul>
            {Object.entries(FACTOR_LABELS).map(([key, label]) => (
              <li key={key}>
                <strong>{label}:</strong>{' '}
                {key === 'quantity' ? factors[key].count : `${factors[key].score} out of 100`}.{' '}
                {factors[key].detail}
              </li>
            ))}
            {notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

export default function App() {
  const[question, setQuestion] = useState('')
  const[messages, setMessages] = useState([])
  const[isLoading, setIsLoading] = useState(false)
  const[error, setError] = useState('')
  const [activeTab, setActiveTab] = useState("chat");

  const conversationEndRef = useRef(null)

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [messages, isLoading])

  async function handleSubmit(event) {
    event.preventDefault()

    if (isLoading) return
    
    const submittedQuestion = question.trim()

    if (!submittedQuestion) {
      setError('Please enter a question or describe a suspicious message.')
      return
    }

    setError('')
    setIsLoading(true)

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text: submittedQuestion,
    }

    setMessages((previous) => [...previous, userMessage])
    setQuestion('')

    try {
      const data = await getAnswer(submittedQuestion)

      if (typeof data.answer !== 'string' || !data.answer.trim()) {
        throw new Error('The response did not contain an answer.')
      }

      const assistantMessage = {
        id: crypto.randomUUID(), role: 'assistant',
        text: data.answer, sources: data.sources ?? [],
        confidence: data.confidence ?? null,
      }

      setMessages((previous) => [...previous, assistantMessage])
    } catch (err) {
      setError(
        err.message && err.message !== 'Request failed'
          ? err.message
          : 'We could not get an answer. Please try again.',
      )
      setQuestion(submittedQuestion)
      setMessages((previous) => previous.filter((m) => m.id !== userMessage.id))
    } finally {
      setIsLoading(false)
    }
  }

  return (

    <main className="chat-page">
      <header>
        <h1>Scam Support Chat</h1>
        <p>Describe or paste a suspicious call, email, or text to see if it is trustworthy.</p>
        <p className="demo-notice">
          This tool points out warning signs. It cannot guarantee a message is safe.
          Don't paste passwords or account numbers.
        </p>
      </header>

      <div className="app-tabs">
        <button onClick={() => setActiveTab("chat")}>
          Chatbot
        </button>

        <button onClick={() => setActiveTab("developer")}>
          For Developers
        </button>
      </div>

      {activeTab === "chat" && (
        <>
          <section
            className="conversation"
            aria-label="Conversation"
            role="log"
            aria-relevant="additions"
          >

          {messages.length === 0 && (
            <p className="empty-message">
              Try asking "How can I recognize a fake bank text?"
            </p>
          )}

                {messages.map((message) => (
          <article key={message.id} className={`message message-${message.role}`}>
            <strong>{message.role === 'user' ? 'You' : 'Scam Support'}</strong>
            <p style={{ whiteSpace: 'pre-wrap' }}>{message.text}</p>
            {message.confidence && <ConfidenceSummary confidence={message.confidence} />}
            {message.sources?.length > 0 && (
              <section aria-label="Sources used for this answer">
                <h2>Sources</h2>
                <ol>
                  {[...message.sources]
                    .sort((a, b) => Number(b.cited) - Number(a.cited))
                    .map((s) => (
                      <li key={s.id} value={s.id}>
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.publisher}: {s.title}
                        </a>
                        {!s.cited && ' (also consulted)'}
                        {s.authority && (
                          <span className="source-authority">
                            {' '}· {s.authority}
                            {s.reliability_notes?.length > 0 && ` (${s.reliability_notes.join('; ')})`}
                          </span>
                        )}
                        <details><summary>Show the passage used</summary><p>{s.snippet}</p></details>
                      </li>
                    ))}
                </ol>
              </section>
            )}
          </article>
        ))}
      </section>
      <p role="status">
          {isLoading ? 'Checking your question...' : ''}
      </p>
      
      <form onSubmit={handleSubmit}>
        <label htmlFor="question">Your question or suspicious message:</label>

        <textarea
          id="question"
          value={question}
          onChange={(event) => {
            setQuestion(event.target.value)
            setError('')
          }}
          rows={5}
          disabled={isLoading}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? 'question-error' : undefined}
        />
        {error && (
          <p id="question-error" className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Waiting for an answer...' : 'Send question'}
        </button>
      </form>
      <div ref={conversationEndRef} />
      </>
      )}
      {/* DEVELOPER PAGE */}
      {activeTab === "developer" && (
        <DeveloperPage />
      )}

    </main>
  )
}