import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { MessageSquare, Search, Send } from 'lucide-react'
import LoadingHint from '../components/ui/LoadingHint.jsx'
import { api } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'

function StarPicker({ value, onChange }) {
  const [hovered, setHovered] = useState(0)
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((s) => (
        <button
          key={s}
          type="button"
          onMouseEnter={() => setHovered(s)}
          onMouseLeave={() => setHovered(0)}
          onClick={() => onChange(s)}
          className={`text-2xl transition-colors ${s <= (hovered || value) ? 'text-amber-400' : 'text-slate-700'}`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

function ReviewPanel({ exchangeId, userId }) {
  const [reviews, setReviews] = useState(null)
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.exchangeReviews(exchangeId).then(setReviews).catch(() => setReviews([]))
  }, [exchangeId])

  const myReview = reviews?.find((r) => r.reviewer_id === userId)
  const canReview = reviews !== null && !myReview

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!rating) return
    setSubmitting(true)
    setError(null)
    try {
      await api.submitReview(exchangeId, rating, comment.trim() || null)
      const updated = await api.exchangeReviews(exchangeId)
      setReviews(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (reviews === null) return null

  return (
    <div className="border-t border-white/5 bg-slate-900/60 px-4 py-4 sm:px-6">
      {myReview ? (
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">Ваш отзыв:</span>
          <span className="text-amber-400">{'★'.repeat(myReview.rating)}{'☆'.repeat(5 - myReview.rating)}</span>
          {myReview.comment ? <span className="text-xs text-slate-400 truncate">{myReview.comment}</span> : null}
        </div>
      ) : canReview ? (
        <form onSubmit={handleSubmit}>
          <p className="mb-3 text-xs font-black uppercase tracking-widest text-slate-400">
            Оставить отзыв о сделке
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="space-y-2">
              <StarPicker value={rating} onChange={setRating} />
              <input
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Комментарий (необязательно)"
                className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white outline-none focus:border-indigo-500 sm:w-72"
              />
            </div>
            <button
              type="submit"
              disabled={!rating || submitting}
              className="shrink-0 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500 disabled:opacity-40"
            >
              {submitting ? '…' : 'Отправить'}
            </button>
          </div>
          {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}
        </form>
      ) : (
        <p className="text-xs text-slate-500">Сделка завершена</p>
      )}
    </div>
  )
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

const statusLabel = {
  discussion: 'Обсуждение',
  active: 'Active Swap',
  completed: 'Завершено',
  cancelled: 'Отменено',
}

function MessagesPage() {
  const { isAuthenticated, userId } = useAuth()
  const location = useLocation()
  const targetUserId = location.state?.targetUserId ?? null
  const [exchanges, setExchanges] = useState([])
  const [incomingInterests, setIncomingInterests] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState(null)
  const [loadingList, setLoadingList] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const wsRef = useRef(null)
  const bottomRef = useRef(null)
  // Кэш exchange_id → chat_id, не вызывает ре-рендер
  const chatIdCache = useRef({})

  // ── Загрузка списка сделок ─────────────────────────────────────────────────
  const loadExchanges = useCallback(async () => {
    setLoadingList(true)
    setError(null)
    try {
      const [ex, incoming] = await Promise.all([api.myExchanges(), api.incomingInterests()])
      setIncomingInterests(incoming)
      setExchanges(ex)
      setSelectedId((prev) => {
        // При переходе с матчейкинга всегда выбираем обмен с нужным пользователем
        if (targetUserId != null) {
          const target = ex.find(
            (e) => e.initiator_id === targetUserId || e.partner_id === targetUserId,
          )
          // Нашли обмен — открываем его; не нашли — null (покажем подсказку)
          return target ? target.id : null
        }
        if (prev != null && ex.some((e) => e.id === prev)) return prev
        return ex[0]?.id ?? null
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingList(false)
    }
  }, [isAuthenticated, targetUserId])

  useEffect(() => {
    ;(async () => {
      await loadExchanges()
    })()
  }, [loadExchanges])

  // ── Загрузка сообщений ─────────────────────────────────────────────────────
  const loadMessages = useCallback(
    async (exchangeId) => {
      if (!exchangeId || !isAuthenticated) return
      setLoadingMsg(true)
      setError(null)
      try {
        const list = await api.chatMessages(exchangeId)
        setMessages(list)
      } catch (e) {
        setError(e.message)
        setMessages([])
      } finally {
        setLoadingMsg(false)
      }
    },
    [isAuthenticated],
  )

  useEffect(() => {
    if (selectedId == null) return

    ;(async () => {
      await loadMessages(selectedId)
    })()
  }, [selectedId, loadMessages])

  // ── WebSocket ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated || !selectedId || !userId) return

    let ws = null
    let cancelled = false

    // Очищаем кэш предыдущего чата при смене сделки
    chatIdCache.current = {}

    const connect = async () => {
      // Получаем реальный chat_id для WS (кэшируем в ref чтобы не вызывать лишних ре-рендеров)
      let chatId = chatIdCache.current[selectedId]
      if (!chatId) {
        try {
          const chat = await api.getChatByExchange(selectedId)
          chatId = chat.id
          chatIdCache.current[selectedId] = chatId
        } catch {
          // Чат ещё не создан — WS не подключаем, HTTP-отправка работает
          return
        }
      }
      if (cancelled) return

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const host = window.location.host
      const token = localStorage.getItem('ssn_token')
      ws = new WebSocket(`${proto}://${host}/api/v1/chat/${chatId}/ws?token=${token}`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'exchange_update') {
          // Обновляем состояние сделки, сохраняя partner_id/partner_name текущего пользователя
          setExchanges((prev) =>
            prev.map((ex) => {
              if (ex.id !== data.exchange.id) return ex
              // eslint-disable-next-line no-unused-vars
              const { partner_id, partner_name, ...statusFields } = data.exchange
              return { ...ex, ...statusFields }
            }),
          )
        } else {
          setMessages((prev) => [...prev, data])
        }
      }

      ws.onerror = () => {
        // WS недоступен — HTTP-отправка продолжает работать
      }
    }

    void connect()

    return () => {
      cancelled = true
      ws?.close()
      wsRef.current = null
    }
  }, [isAuthenticated, selectedId, userId])

  // Автоскролл вниз при новых сообщениях
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Отправка ──────────────────────────────────────────────────────────────
  const send = async () => {
    const text = draft.trim()
    if (!text || !selectedId) return
    try {
      const newMessage = await api.sendChatMessage(selectedId, text)
      setDraft('')
      // Если WebSocket не подключен, добавляем сообщение в стейт локально
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setMessages((prev) => [...prev, newMessage])
      }
      // Если WebSocket работает, сообщение придет через onmessage
    } catch (e) {
      setError(e.message)
    }
  }

  const startExchange = async () => {
    if (!selectedId) return
    try {
      await api.requestStartExchange(selectedId)
      await loadExchanges()
    } catch (e) {
      setError(e.message)
    }
  }

  // Определяем статус для текущего пользователя
  const getStartStatus = () => {
    if (!selected) return null
    const isInitiator = selected.initiator_id === userId
    const iConfirmed = selected.started_by_initiator
    const pConfirmed = selected.started_by_partner

    if (isInitiator) {
      if (iConfirmed && pConfirmed) return 'both_confirmed'
      if (iConfirmed) return 'waiting_partner'
      if (pConfirmed) return 'partner_waiting_you'
      return 'ready_to_start'
    } else {
      if (iConfirmed && pConfirmed) return 'both_confirmed'
      if (pConfirmed) return 'waiting_partner'
      if (iConfirmed) return 'partner_waiting_you'
      return 'ready_to_start'
    }
  }

  const confirmDone = async () => {
    if (!selectedId) return
    setActionBusy(true)
    setError(null)
    try {
      await api.confirmExchangeCompletion(selectedId)
      await loadExchanges()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionBusy(false)
    }
  }

  // Принять входящий отклик на своё объявление — создаётся сделка, она появится в списке слева
  const acceptIncoming = async (listingId, responderId) => {
    setActionBusy(true)
    setError(null)
    try {
      await api.acceptInterest(listingId, responderId)
      await loadExchanges()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionBusy(false)
    }
  }

  const selected = exchanges.find((e) => e.id === selectedId)
  const title = selected?.partner_name
    ? `${selected.partner_name} (#${selected.id})`
    : selected
      ? `Сделка #${selected.id}`
      : ''

  // ── Пустое состояние — нет авторизации ────────────────────────────────────
  if (!isAuthenticated) {
    return (
      <div className="animate-page flex h-[min(700px,calc(100vh-10rem))] items-center justify-center rounded-[40px] border border-white/5 bg-slate-950/50">
        <div className="text-center">
          <MessageSquare className="mx-auto mb-4 text-slate-600" size={48} />
          <p className="text-sm font-bold text-slate-400">Войдите, чтобы видеть сообщения</p>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-page flex h-[min(700px,calc(100vh-10rem))] flex-col overflow-hidden rounded-[40px] border border-white/5 bg-slate-950/50 backdrop-blur-md md:flex-row">
      {/* ── Сайдбар ── */}
      <div className="flex w-full shrink-0 flex-col border-white/5 bg-slate-900/30 md:w-80 md:border-r">
        <div className="p-6">
          <h2 className="mb-4 text-xl font-black italic text-white">MESSAGES</h2>
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-slate-500"
              aria-hidden
            />
            <input
              type="search"
              placeholder="Поиск сделок..."
              className="w-full rounded-xl border border-white/10 bg-white/5 py-2 pl-9 pr-4 text-xs text-white outline-none ring-indigo-500 focus:ring-1"
            />
          </div>
        </div>

        <div className="custom-scrollbar flex-1 overflow-y-auto px-3 pb-4">
          {incomingInterests.length > 0 ? (
            <div className="mb-3 space-y-2 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-3">
              <p className="px-1 text-[10px] font-black uppercase tracking-widest text-amber-400">
                Входящие отклики ({incomingInterests.length})
              </p>
              {incomingInterests.map((it) => (
                <div key={it.id} className="rounded-xl border border-white/5 bg-white/5 p-3">
                  <p className="truncate text-xs font-bold text-white">
                    {it.responder_full_name ?? `Пользователь #${it.responder_id}`}
                  </p>
                  <p className="mt-0.5 truncate text-[10px] text-slate-500">
                    на «{it.listing_title}»
                  </p>
                  {it.message ? (
                    <p className="mt-1 line-clamp-2 text-[11px] text-slate-400">{it.message}</p>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => acceptIncoming(it.listing_id, it.responder_id)}
                    disabled={actionBusy}
                    className="mt-2 w-full rounded-lg bg-indigo-600 py-1.5 text-[10px] font-black uppercase tracking-widest text-white transition hover:bg-indigo-500 disabled:opacity-50"
                  >
                    Принять отклик
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          {loadingList ? (
            <div className="px-2">
              <LoadingHint label="Загрузка…" />
            </div>
          ) : exchanges.length === 0 ? (
            <div className="px-2 py-8 text-center">
              <MessageSquare className="mx-auto mb-3 text-slate-700" size={32} />
              <p className="text-xs text-slate-500">
                У вас пока нет активных сделок.
                <br />
                Откликнитесь на объявление на странице Сделки.
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {exchanges.map((ex) => {
                const name = ex.partner_name
                  ? `${ex.partner_name} (#${ex.id})`
                  : `Обмен #${ex.id}`
                return (
                  <button
                    key={ex.id}
                    type="button"
                    onClick={() => setSelectedId(ex.id)}
                    className={`flex w-full items-center space-x-3 rounded-2xl p-4 text-left transition-all ${
                      selectedId === ex.id
                        ? 'border border-indigo-500/20 bg-indigo-600/10'
                        : 'border border-transparent hover:bg-white/5'
                    }`}
                  >
                    <div
                      className={`flex size-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold ${
                        selectedId === ex.id
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {name.charAt(0)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p
                        className={`truncate text-xs font-bold ${
                          selectedId === ex.id ? 'text-white' : 'text-slate-300'
                        }`}
                      >
                        {name}
                      </p>
                      <p className="mt-1 truncate text-[10px] font-medium text-slate-500">
                        {statusLabel[ex.status] ?? ex.status}
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Область чата ── */}
      <div className="flex min-h-0 flex-1 flex-col bg-slate-900/10">
        {selectedId == null ? (
          <div className="flex flex-1 items-center justify-center px-6">
            {targetUserId != null ? (
              <div className="text-center">
                <MessageSquare className="mx-auto mb-3 text-slate-600" size={32} />
                <p className="text-sm font-bold text-slate-400">Нет общей сделки</p>
                <p className="mt-2 text-xs text-slate-500">
                  Чтобы написать этому пользователю, сначала откликнитесь на его объявление
                  на странице Сделки.
                </p>
              </div>
            ) : (
              <p className="text-sm text-slate-500">Выберите сделку слева</p>
            )}
          </div>
        ) : (
          <>
            {/* Шапка */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 p-4 sm:p-6">
              <div className="flex min-w-0 items-center space-x-4">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-lg font-black text-white">
                  {title.charAt(0)}
                </div>
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-bold text-white">{title}</h3>
                  <div className="flex items-center space-x-2">
                    <span className="size-1.5 shrink-0 rounded-full bg-green-500" />
                    <span className="truncate text-[10px] font-bold uppercase tracking-widest text-slate-500">
                      {selected ? (statusLabel[selected.status] ?? selected.status) : ''}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selected?.status === 'discussion' ? (() => {
                  const startStatus = getStartStatus()
                  if (startStatus === 'waiting_partner') {
                    return (
                      <span className="rounded-xl bg-slate-700 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-slate-400">
                        Ожидаем подтверждения
                      </span>
                    )
                  }
                  if (startStatus === 'partner_waiting_you') {
                    return (
                      <button
                        type="button"
                        onClick={startExchange}
                        className="rounded-xl bg-amber-500 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-white shadow-lg shadow-amber-500/20 transition hover:bg-amber-400 animate-pulse"
                      >
                        Подтвердить начало
                      </button>
                    )
                  }
                  return (
                    <button
                      type="button"
                      onClick={startExchange}
                      className="rounded-xl bg-amber-600 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-white shadow-lg shadow-amber-500/20 transition hover:bg-amber-500"
                    >
                      Начать обмен
                    </button>
                  )
                })() : selected?.status === 'active' ? (
                  <button
                    type="button"
                    onClick={confirmDone}
                    disabled={actionBusy}
                    className="rounded-xl bg-indigo-600 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:opacity-50"
                  >
                    {actionBusy ? 'Подтверждаем…' : 'Подтвердить выполнение'}
                  </button>
                ) : null}
              </div>
            </div>

            {error ? (
              <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-200">
                {error}
              </div>
            ) : null}

            {/* Сообщения */}
            <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
              {loadingMsg ? (
                <LoadingHint label="Загрузка сообщений…" />
              ) : messages.length === 0 ? (
                <p className="text-xs text-slate-500">Пока нет сообщений — напишите первым.</p>
              ) : (
                messages.map((msg) => {
                  const mine = msg.sender_id === userId
                  return (
                    <div
                      key={msg.id}
                      className={`max-w-[85%] text-sm leading-relaxed sm:max-w-[60%] ${
                        mine
                          ? 'ml-auto rounded-3xl rounded-tr-none bg-indigo-600 p-4 text-white shadow-2xl shadow-indigo-500/20'
                          : 'rounded-3xl rounded-tl-none border border-white/5 bg-white/5 p-4 text-slate-200 shadow-xl'
                      }`}
                    >
                      {msg.content}
                      <p
                        className={`mt-2 font-mono text-[9px] ${mine ? 'text-right text-indigo-300' : 'text-slate-500'}`}
                      >
                        {formatTime(msg.created_at)}
                        {mine ? ' • Отправлено' : ''}
                      </p>
                    </div>
                  )
                })
              )}
              <div ref={bottomRef} />
            </div>

            {selected?.status === 'completed' ? (
              <ReviewPanel exchangeId={selected.id} userId={userId} />
            ) : null}

            {/* Ввод */}
            <div className="border-t border-white/5 bg-slate-900/50 p-4 sm:p-6">
              <div className="flex items-center space-x-2 rounded-[24px] border border-white/10 bg-white/5 p-2">
                <input
                  type="text"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void send()
                    }
                  }}
                  placeholder="Введите сообщение..."
                  className="min-w-0 flex-1 border-none bg-transparent px-2 text-sm text-white outline-none ring-0 placeholder:text-slate-600"
                />
                <button
                  type="button"
                  onClick={() => void send()}
                  disabled={!draft.trim()}
                  className="rounded-2xl bg-indigo-600 p-3 text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:opacity-40"
                  aria-label="Отправить"
                >
                  <Send size={18} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default MessagesPage
