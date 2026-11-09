import { useEffect, useRef, useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'

async function getAnswer(question) {
  await new Promise((resolve) => setTimeout(resolve, 800))

  return {
    answer:
      `Demo reponse to your question: "${question}"\n\n` +
      'The real scam guidance will appear here once the backend is connected.',
  }
}

export default function App() {
  const[question, setQuestion] = useState('')
  const[messages, setMessages] = useState([])
  const[isLoading, setIsLoading] = useState(false)
  const[error, setError] = useState('')

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
        id: crypto.randomUUID(),
        role: 'assistant',
        text: data.answer,
      }

      setMessages((previous) => [...previous, assistantMessage])
    } catch {
      setError('We could not get an answer. Your question is ready to try again.')
      setQuestion(submittedQuestion)
      setMessages((previous) =>
        previous.filter((message) => message.id !== userMessage.id),
      )
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
          Development demo -- all replies are placeholders for actual responses.
        </p>
      </header>

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
            <strong>
              {message.role === 'user' ? 'You' : 'Scam Support'}
            </strong>
            <p>{message.text}</p>
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
    </main>
  )
}