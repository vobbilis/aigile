import { useState } from 'react'

interface Props {
  tags: string[]
  onTagsChange: (tags: string[]) => void
}

export function TagFilterBar({ tags, onTagsChange }: Props) {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleAdd = () => {
    const trimmed = input.trim()
    if (!trimmed.includes(':')) {
      setError('Tag must contain a colon (e.g. env:prod)')
      return
    }
    if (tags.includes(trimmed)) {
      setError('Tag already added')
      return
    }
    setError(null)
    onTagsChange([...tags, trimmed])
    setInput('')
  }

  const handleRemove = (tag: string) => {
    onTagsChange(tags.filter((t) => t !== tag))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAdd()
    }
  }

  return (
    <div className="tag-filter-bar">
      <div className="tag-filter-input">
        <input
          type="text"
          placeholder="Filter by tag (e.g. env:prod)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button type="button" onClick={handleAdd}>
          Add Filter
        </button>
      </div>
      {error && <span className="error">{error}</span>}
      {tags.length > 0 && (
        <div className="tag-chips">
          {tags.map((tag) => (
            <span key={tag} className="tag-chip">
              {tag}
              <button type="button" onClick={() => handleRemove(tag)} aria-label={`Remove ${tag}`}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
