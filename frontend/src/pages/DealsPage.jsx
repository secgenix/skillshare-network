import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Briefcase, Plus, Search, X } from 'lucide-react'
import { api } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import LoadingHint from '../components/ui/LoadingHint.jsx'

// Простой debounce без лишних зависимостей
function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

// ── Модалка создания объявления ───────────────────────────────────────────────
function CreateListingModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    offering_summary: '',
    seeking_summary: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const set = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.createListing({
        title: form.title.trim(),
        description: form.description.trim() || null,
        offering_summary: form.offering_summary.trim(),
        seeking_summary: form.seeking_summary.trim(),
      })
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-[32px] border border-white/10 bg-slate-900 p-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
          aria-label="Закрыть"
        >
          <X size={20} />
        </button>

        <h3 className="mb-6 text-xl font-black italic text-white">Новое объявление</h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">
              Название *
            </label>
            <input
              value={form.title}
              onChange={set('title')}
              required
              placeholder="Например: Обучение Python за дизайн"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none ring-indigo-500 focus:ring-1"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">
              Что предлагаете *
            </label>
            <input
              value={form.offering_summary}
              onChange={set('offering_summary')}
              required
              placeholder="Например: 10 часов менторства по Python"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none ring-indigo-500 focus:ring-1"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">
              Что ищете *
            </label>
            <input
              value={form.seeking_summary}
              onChange={set('seeking_summary')}
              required
              placeholder="Например: UI/UX дизайн лендинга"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none ring-indigo-500 focus:ring-1"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">
              Описание
            </label>
            <textarea
              value={form.description}
              onChange={set('description')}
              rows={3}
              placeholder="Подробнее о вашем предложении (необязательно)"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none ring-indigo-500 focus:ring-1"
            />
          </div>

          {error ? (
            <p className="text-xs text-red-400">{error}</p>
          ) : null}

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving ? 'Создаём…' : 'Создать объявление'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-white/10 px-6 py-3 text-xs font-bold text-slate-400 transition hover:bg-white/5"
            >
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function DealsPage() {
  const { isAuthenticated, userId, openAuthModal } = useAuth()
  const location = useLocation()
  const [listings, setListings] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)

  // Фильтрация с debounce через useMemo
  const filteredListings = useMemo(() => {
    if (!debouncedSearch.trim()) return listings
    const term = debouncedSearch.toLowerCase()
    return listings.filter(
      (l) =>
        l.title?.toLowerCase().includes(term) ||
        l.offering_summary?.toLowerCase().includes(term) ||
        l.seeking_summary?.toLowerCase().includes(term) ||
        l.description?.toLowerCase().includes(term)
    )
  }, [listings, debouncedSearch])
  const [error, setError] = useState(null)
  const [selectedListing, setSelectedListing] = useState(null)
  const [respondMessage, setRespondMessage] = useState('')
  const [responding, setResponding] = useState(false)
  const [createOpen, setCreateOpen] = useState(() => Boolean(location.state?.openCreate))

  const loadListings = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.listings({ status: 'published' })
      setListings(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    ;(async () => {
      await loadListings()
    })()
  }, [])

  const handleRespond = async () => {
    if (!selectedListing) return
    setResponding(true)
    setError(null)
    try {
      await api.respondToListing(selectedListing.id, respondMessage.trim() || null)
      setSelectedListing(null)
      setRespondMessage('')
      await loadListings()
    } catch (e) {
      setError(e.message)
    } finally {
      setResponding(false)
    }
  }

  const handleCreated = async () => {
    setCreateOpen(false)
    await loadListings()
  }

  return (
    <div className="animate-page space-y-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-black italic text-white sm:text-3xl">DEALS</h2>
          <p className="mt-2 text-xs font-medium text-slate-500">
            Активные объявления в сети. Откликайтесь и создавайте сделки.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (!isAuthenticated) {
              openAuthModal()
              return
            }
            setCreateOpen(true)
          }}
          className="flex w-fit items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500"
        >
          <Plus size={16} />
          Создать объявление
        </button>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          {error}
        </div>
      ) : null}

      <div className="rounded-[40px] border border-white/5 bg-slate-900 p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="relative flex-1">
            <Search
              className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500"
              aria-hidden
            />
            <input
              type="search"
              placeholder="Поиск по навыкам, названию..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 py-2 pl-10 pr-4 text-sm text-white outline-none ring-indigo-500 focus:ring-1"
            />
          </div>
        </div>

        {loading ? (
          <div className="py-12">
            <LoadingHint label="Загружаем объявления…" />
          </div>
        ) : filteredListings.length === 0 ? (
          <div className="flex min-h-[300px] items-center justify-center">
            <div className="text-center">
              <Briefcase className="mx-auto mb-4 text-slate-700" size={48} />
              <p className="text-sm font-bold text-slate-400">
                {listings.length === 0 ? 'Объявлений пока нет' : 'Ничего не найдено'}
              </p>
              <p className="mt-2 text-xs text-slate-600">
                {listings.length === 0
                  ? 'Создайте первое объявление и начните обмениваться навыками.'
                  : 'Попробуйте изменить поисковый запрос.'}
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredListings.map((listing) => {
              const isOwn = listing.author_id === userId
              return (
                <div
                  key={listing.id}
                  className="group relative overflow-hidden rounded-2xl border border-white/5 bg-white/5 p-6 transition hover:border-indigo-500/30 hover:bg-white/10"
                >
                  <div className="mb-4 flex items-start justify-between">
                    <div className="flex size-10 items-center justify-center rounded-xl bg-indigo-600 text-sm font-black text-white">
                      {listing.title.charAt(0)}
                    </div>
                    {isOwn ? (
                      <span className="rounded-full border border-green-500/20 bg-green-500/10 px-2 py-0.5 text-[9px] font-bold uppercase text-green-400">
                        Моё
                      </span>
                    ) : null}
                  </div>
                  <h3 className="mb-2 text-sm font-bold text-white">{listing.title}</h3>
                  {listing.description ? (
                    <p className="mb-3 line-clamp-2 text-xs text-slate-400">
                      {listing.description}
                    </p>
                  ) : null}
                  <div className="space-y-2 text-xs">
                    <p className="text-slate-500">
                      <span className="font-bold text-indigo-400">Предлагает:</span>{' '}
                      {listing.offering_summary}
                    </p>
                    <p className="text-slate-500">
                      <span className="font-bold text-fuchsia-400">Ищет:</span>{' '}
                      {listing.seeking_summary}
                    </p>
                  </div>
                  {!isOwn && isAuthenticated ? (
                    <button
                      type="button"
                      onClick={() => setSelectedListing(listing)}
                      className="mt-4 w-full rounded-xl bg-indigo-600 py-2 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500"
                    >
                      Откликнуться
                    </button>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Модалка отклика */}
      {selectedListing ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[120] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
          onClick={() => setSelectedListing(null)}
        >
          <div
            className="relative w-full max-w-md rounded-[32px] border border-white/10 bg-slate-900 p-8 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setSelectedListing(null)}
              className="absolute right-4 top-4 rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
              aria-label="Закрыть"
            >
              <X size={20} />
            </button>

            <h3 className="mb-2 text-xl font-black italic text-white">
              {selectedListing.title}
            </h3>
            <p className="mb-6 text-xs text-slate-400">
              Отправьте сообщение автору объявления. После принятия откроется чат.
            </p>

            <textarea
              value={respondMessage}
              onChange={(e) => setRespondMessage(e.target.value)}
              placeholder="Расскажите, почему вы подходите для этого обмена (необязательно)"
              rows={4}
              className="mb-4 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none ring-indigo-500 focus:ring-1"
            />

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleRespond}
                disabled={responding}
                className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500 disabled:opacity-50"
              >
                {responding ? 'Отправляем…' : 'Откликнуться'}
              </button>
              <button
                type="button"
                onClick={() => setSelectedListing(null)}
                className="rounded-xl border border-white/10 px-6 py-3 text-xs font-bold text-slate-400 transition hover:bg-white/5"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {/* Модалка создания объявления */}
      {createOpen ? (
        <CreateListingModal onClose={() => setCreateOpen(false)} onCreated={handleCreated} />
      ) : null}
    </div>
  )
}

export default DealsPage
