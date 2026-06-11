import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import LoadingHint from '../components/ui/LoadingHint.jsx'
import { api } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'

const statusProgress = {
  discussion: 25,
  active: 70,
  completed: 100,
  cancelled: 0,
}

const statusLabel = {
  discussion: 'Обсуждение',
  active: 'Активный обмен',
  completed: 'Завершена',
  cancelled: 'Отменена',
}

const logTypeColor = {
  active: 'bg-indigo-500',
  completed: 'bg-green-500',
  discussion: 'bg-amber-500',
  cancelled: 'bg-slate-500',
}

function formatLogTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  if (diff < 86400000) return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  if (diff < 172800000) return 'Вчера'
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
}

function DashboardPage() {
  const { isAuthenticated } = useAuth()
  const [profile, setProfile] = useState(null)
  const [allExchanges, setAllExchanges] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) return
    let cancelled = false
    queueMicrotask(() => {
      void (async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const [ex, me] = await Promise.all([api.myExchanges(), api.getMe()])
        if (cancelled) return
        setAllExchanges(ex)
        setProfile(me)
        setLoadError(null)
      } catch (e) {
        if (!cancelled) setLoadError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
      })()
    })
    return () => { cancelled = true }
  }, [isAuthenticated])

  const activeExchanges = useMemo(
    () => allExchanges.filter((e) => e.status === 'discussion' || e.status === 'active'),
    [allExchanges],
  )

  const swaps = useMemo(
    () =>
      activeExchanges.slice(0, 4).map((ex) => ({
        id: ex.id,
        title: ex.partner_name ? `Обмен с ${ex.partner_name}` : `Сделка #${ex.id}`,
        partner: statusLabel[ex.status] ?? ex.status,
        progress: statusProgress[ex.status] ?? 40,
      })),
    [activeExchanges],
  )

  const logs = useMemo(() => {
    if (!isAuthenticated || allExchanges.length === 0) return []
    return [...allExchanges]
      .sort((a, b) => new Date(b.started_at ?? b.created_at) - new Date(a.started_at ?? a.created_at))
      .slice(0, 6)
      .map((ex) => ({
        text: ex.partner_name
          ? `Сделка с ${ex.partner_name} — ${statusLabel[ex.status] ?? ex.status}`
          : `Сделка #${ex.id} — ${statusLabel[ex.status] ?? ex.status}`,
        time: formatLogTime(ex.started_at ?? ex.created_at),
        type: ex.status,
      }))
  }, [isAuthenticated, allExchanges])

  const completedCount = allExchanges.filter((e) => e.status === 'completed').length
  const trustScore = profile?.rating ? Number(profile.rating).toFixed(2) : null

  return (
    <div className="animate-page mt-6 grid grid-cols-1 gap-8 lg:mt-10 lg:grid-cols-3">
      <div className="space-y-8 lg:col-span-2">
        {loadError ? (
          <p className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            {loadError}
          </p>
        ) : null}
        {isAuthenticated && loading ? <LoadingHint label="Загружаем данные…" /> : null}
        {!isAuthenticated ? (
          <p className="text-sm text-slate-500">
            Войдите в профиль, чтобы увидеть активные сделки.
          </p>
        ) : null}

        {/* Hero */}
        <div className="group relative overflow-hidden rounded-[40px] border border-white/5 bg-slate-900 p-10 text-white shadow-2xl">
          <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/10 to-transparent opacity-0 transition-opacity duration-700 group-hover:opacity-100" />
          <div className="relative z-10 flex flex-col items-center justify-between gap-8 md:flex-row">
            <div className="text-center md:text-left">
              <span className="inline-block rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-bold uppercase tracking-widest text-indigo-400">
                {completedCount > 0 ? `${completedCount} завершённых обменов` : 'Добро пожаловать'}
              </span>
              <h1 className="mt-4 text-4xl font-black uppercase italic leading-none tracking-tighter text-white sm:text-5xl">
                {profile?.full_name ? (
                  <>Привет,<br /><span className="text-indigo-400">{profile.full_name.split(' ')[0]}</span></>
                ) : (
                  <>Skill<br /><span className="text-indigo-400">Share</span></>
                )}
              </h1>
              <p className="mt-4 max-w-sm font-medium text-slate-400">
                {activeExchanges.length > 0
                  ? `У вас ${activeExchanges.length} активных сделок. Продолжайте обмены!`
                  : 'Найдите партнёра через матчмейкинг и начните первый обмен навыками.'}
              </p>
            </div>
            <div className="shrink-0 rotate-3 rounded-[32px] border border-white/10 bg-slate-800 p-8 shadow-2xl transition-transform duration-500 group-hover:rotate-0">
              <div className="text-4xl font-black text-indigo-400">
                {trustScore ?? '—'}
              </div>
              <div className="mt-1 text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Trust Score
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Active Swaps */}
          <div className="rounded-[32px] border border-white/5 bg-slate-900/50 p-8 backdrop-blur-md">
            <h3 className="mb-6 text-lg font-bold uppercase italic text-white">Active Swaps</h3>
            {swaps.length === 0 ? (
              <p className="text-sm text-slate-500">
                {isAuthenticated ? 'Нет активных сделок.' : 'Войдите, чтобы увидеть сделки.'}
              </p>
            ) : (
              <div className="space-y-4">
                {swaps.map((swap) => (
                  <div
                    key={swap.id}
                    className="rounded-2xl border border-white/5 bg-white/5 p-4 transition hover:border-indigo-500/30"
                  >
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-bold text-white">{swap.title}</p>
                        <p className="text-[10px] text-slate-500">{swap.partner}</p>
                      </div>
                      <div className="font-mono text-[10px] text-indigo-400">{swap.progress}%</div>
                    </div>
                    <div className="h-1 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="h-full bg-indigo-500 transition-all duration-1000"
                        style={{ width: `${swap.progress}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Matching Pulse */}
          <div className="flex flex-col justify-between rounded-[32px] bg-gradient-to-br from-indigo-600 to-fuchsia-600 p-8 shadow-2xl shadow-indigo-500/20">
            <h3 className="text-lg font-bold uppercase italic text-white">
              Matching<br />Pulse
            </h3>
            <p className="text-sm font-medium text-white/80">
              Алгоритм матчмейкинга анализирует навыки и подбирает лучших партнёров для обмена.
            </p>
            <Link
              to="/matching"
              className="mt-4 w-full rounded-xl bg-white py-3 text-center text-xs font-black uppercase tracking-widest text-indigo-900 shadow-xl transition-transform hover:scale-105 active:scale-95"
            >
              Открыть граф
            </Link>
          </div>
        </div>
      </div>

      {/* System Logs */}
      <div className="space-y-6">
        <div className="h-full rounded-[40px] border border-white/5 bg-slate-900 p-8 shadow-2xl">
          <h3 className="mb-6 text-sm font-black uppercase italic tracking-widest text-white">
            Activity
          </h3>
          {logs.length === 0 ? (
            <p className="text-xs text-slate-500">
              {isAuthenticated ? 'Активности пока нет.' : 'Войдите, чтобы видеть активность.'}
            </p>
          ) : (
            <div className="custom-scrollbar max-h-[400px] space-y-6 overflow-y-auto pr-2">
              {logs.map((n, i) => (
                <div
                  key={i}
                  className="flex items-start space-x-3 border-l-2 border-transparent pl-3 transition-all hover:border-indigo-500"
                >
                  <div className={`mt-1.5 size-1.5 shrink-0 rounded-full ${logTypeColor[n.type] ?? 'bg-slate-500'}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs leading-relaxed text-slate-300">{n.text}</p>
                    <span className="mt-1 block font-mono text-[9px] uppercase text-slate-600">{n.time}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <Link
            to="/messages"
            className="mt-8 block w-full rounded-xl border border-white/5 bg-white/5 py-3 text-center text-[10px] font-black uppercase tracking-widest text-white transition hover:bg-white/10"
          >
            Перейти к чатам
          </Link>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
