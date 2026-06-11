import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Award,
  Bell,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  LogOut,
  PlusCircle,
  Settings,
  ShieldCheck,
  UserCheck,
  Zap,
} from 'lucide-react'
import { api } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import LoadingHint from '../components/ui/LoadingHint.jsx'
import { initialsFromName } from '../lib/userDisplay.js'

// Профиль считается заполненным если есть имя
function isProfileComplete(profile) {
  return Boolean(profile?.full_name)
}

function OnboardingBanner({ profile, onSave, mySkills, onSkillsSave }) {
  const [name, setName] = useState(profile?.full_name ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [step, setStep] = useState(profile?.full_name ? 'skills' : 'name')

  // Навыки: [{skill_id, skill_name, level}]
  const [offered, setOffered] = useState(() => mySkills?.offered ?? [])
  const [wanted, setWanted] = useState(() => mySkills?.wanted ?? [])

  const [offeredInput, setOfferedInput] = useState('')
  const [wantedInput, setWantedInput] = useState('')
  const [creating, setCreating] = useState(false)

  const handleSaveName = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      await onSave({ full_name: name.trim() })
      setStep('skills')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleAddOffered = async (e) => {
    e.preventDefault()
    const skillName = offeredInput.trim()
    if (!skillName) return
    setCreating(true)
    setError(null)
    try {
      const skill = await api.createSkill(skillName)
      setOffered(prev => [...prev, { skill_id: skill.id, skill_name: skill.name, level: 2 }])
      setOfferedInput('')
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  const handleAddWanted = async (e) => {
    e.preventDefault()
    const skillName = wantedInput.trim()
    if (!skillName) return
    setCreating(true)
    setError(null)
    try {
      const skill = await api.createSkill(skillName)
      setWanted(prev => [...prev, { skill_id: skill.id, skill_name: skill.name, desired_level: 2 }])
      setWantedInput('')
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  const removeOffered = (skillId) => {
    setOffered(prev => prev.filter(s => s.skill_id !== skillId))
  }

  const removeWanted = (skillId) => {
    setWanted(prev => prev.filter(s => s.skill_id !== skillId))
  }

  const updateOfferedLevel = (skillId, level) => {
    setOffered(prev => prev.map(s => s.skill_id === skillId ? { ...s, level } : s))
  }

  const updateWantedLevel = (skillId, level) => {
    setWanted(prev => prev.map(s => s.skill_id === skillId ? { ...s, desired_level: level } : s))
  }

  const handleSaveSkills = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSkillsSave({
        offered: offered.map(s => ({ skill_id: s.skill_id, level: s.level })),
        wanted: wanted.map(s => ({ skill_id: s.skill_id, desired_level: s.desired_level })),
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (step === 'name') {
    return (
      <div className="rounded-[32px] border border-indigo-500/30 bg-indigo-600/10 p-8">
        <div className="mb-2 flex items-center gap-3">
          <div className="rounded-xl bg-indigo-600 p-2">
            <Zap className="size-5 text-white" />
          </div>
          <h2 className="text-xl font-black uppercase italic text-white">Добро пожаловать</h2>
        </div>
        <p className="mb-6 text-sm text-slate-400">
          Заполните профиль — без этого алгоритм матчинга снизит ваш рейтинг на 15%.
        </p>
        <form onSubmit={handleSaveName} className="flex flex-col gap-3 sm:flex-row">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ваше имя"
            required
            className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={saving || !name.trim()}
            className="rounded-xl bg-indigo-600 px-6 py-3 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {saving ? 'Сохраняем…' : 'Далее'}
          </button>
        </form>
        {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}
      </div>
    )
  }

  // step === 'skills'
  const hasSkills = offered.length > 0 || wanted.length > 0

  return (
    <div className="rounded-[32px] border border-indigo-500/30 bg-indigo-600/10 p-8">
      <div className="mb-2 flex items-center gap-3">
        <div className="rounded-xl bg-indigo-600 p-2">
          <Zap className="size-5 text-white" />
        </div>
        <h2 className="text-xl font-black uppercase italic text-white">Добавьте навыки</h2>
      </div>
      <p className="mb-6 text-sm text-slate-400">
        Укажите что вы предлагаете и что хотите получить — это основа для матчмейкинга.
      </p>

      <div className="space-y-6">
        {/* Что предлагаю */}
        <div>
          <p className="mb-3 text-xs font-black uppercase tracking-widest text-indigo-400">
            Что я предлагаю
          </p>
          <form onSubmit={handleAddOffered} className="mb-3 flex gap-2">
            <input
              value={offeredInput}
              onChange={(e) => setOfferedInput(e.target.value)}
              placeholder="Например: Python, Дизайн, Маркетинг..."
              disabled={creating}
              className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white outline-none focus:border-indigo-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={creating || !offeredInput.trim()}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-indigo-500 disabled:opacity-50"
            >
              {creating ? '…' : '+'}
            </button>
          </form>
          {offered.length > 0 ? (
            <ul className="space-y-2">
              {offered.map(s => (
                <li key={s.skill_id} className="flex items-center gap-2 rounded-xl border border-white/5 bg-white/5 p-3">
                  <span className="flex-1 text-sm font-bold text-white">{s.skill_name}</span>
                  <select
                    value={s.level}
                    onChange={(e) => updateOfferedLevel(s.skill_id, Number(e.target.value))}
                    className="rounded-lg border border-white/10 bg-slate-800 px-2 py-1 text-xs text-white outline-none"
                  >
                    <option value={1}>Начальный</option>
                    <option value={2}>Средний</option>
                    <option value={3}>Продвинутый</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => removeOffered(s.skill_id)}
                    className="text-slate-400 transition hover:text-red-400"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-600">Добавьте хотя бы один навык</p>
          )}
        </div>

        {/* Что хочу получить */}
        <div>
          <p className="mb-3 text-xs font-black uppercase tracking-widest text-fuchsia-400">
            Что я хочу получить
          </p>
          <form onSubmit={handleAddWanted} className="mb-3 flex gap-2">
            <input
              value={wantedInput}
              onChange={(e) => setWantedInput(e.target.value)}
              placeholder="Например: JavaScript, SEO, Копирайтинг..."
              disabled={creating}
              className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white outline-none focus:border-fuchsia-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={creating || !wantedInput.trim()}
              className="rounded-xl bg-fuchsia-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-fuchsia-500 disabled:opacity-50"
            >
              {creating ? '…' : '+'}
            </button>
          </form>
          {wanted.length > 0 ? (
            <ul className="space-y-2">
              {wanted.map(s => (
                <li key={s.skill_id} className="flex items-center gap-2 rounded-xl border border-white/5 bg-white/5 p-3">
                  <span className="flex-1 text-sm font-bold text-white">{s.skill_name}</span>
                  <select
                    value={s.desired_level}
                    onChange={(e) => updateWantedLevel(s.skill_id, Number(e.target.value))}
                    className="rounded-lg border border-white/10 bg-slate-800 px-2 py-1 text-xs text-white outline-none"
                  >
                    <option value={1}>Начальный</option>
                    <option value={2}>Средний</option>
                    <option value={3}>Продвинутый</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => removeWanted(s.skill_id)}
                    className="text-slate-400 transition hover:text-red-400"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-600">Добавьте хотя бы один навык</p>
          )}
        </div>

        {error ? <p className="text-xs text-red-400">{error}</p> : null}

        <button
          type="button"
          onClick={handleSaveSkills}
          disabled={saving || !hasSkills}
          className="w-full rounded-xl bg-indigo-600 px-6 py-3 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? 'Сохраняем…' : 'Сохранить навыки'}
        </button>
      </div>
    </div>
  )
}

function SecuritySection() {
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showCur, setShowCur] = useState(false)
  const [showNext, setShowNext] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (next !== confirm) { setError('Пароли не совпадают'); return }
    setSaving(true); setError(null); setSuccess(false)
    try {
      await api.changePassword(cur, next)
      setSuccess(true); setCur(''); setNext(''); setConfirm('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-[40px] border border-white/5 bg-slate-900 p-8">
      <h3 className="mb-6 text-2xl font-black uppercase italic text-white">Безопасность</h3>
      <form onSubmit={handleSubmit} className="max-w-md space-y-4">
        {[
          { label: 'Текущий пароль', val: cur, set: setCur, show: showCur, toggle: () => setShowCur(v => !v) },
          { label: 'Новый пароль', val: next, set: setNext, show: showNext, toggle: () => setShowNext(v => !v) },
          { label: 'Повторите новый пароль', val: confirm, set: setConfirm, show: showNext, toggle: null },
        ].map(({ label, val, set, show, toggle }) => (
          <div key={label}>
            <label className="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">{label}</label>
            <div className="relative">
              <input
                type={show ? 'text' : 'password'}
                value={val}
                onChange={e => set(e.target.value)}
                required
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none ring-indigo-500 focus:ring-1 pr-10"
              />
              {toggle ? (
                <button type="button" onClick={toggle} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white">
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              ) : null}
            </div>
          </div>
        ))}
        {error ? <p className="text-xs text-red-400">{error}</p> : null}
        {success ? <p className="text-xs text-green-400">Пароль успешно изменён</p> : null}
        <button
          type="submit"
          disabled={saving || !cur || !next || !confirm}
          className="rounded-xl bg-indigo-600 px-6 py-3 text-xs font-black uppercase tracking-widest text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? 'Сохраняем…' : 'Сменить пароль'}
        </button>
      </form>
    </div>
  )
}

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-200 focus:outline-none ${
        checked ? 'bg-indigo-600' : 'bg-slate-700'
      }`}
    >
      <span
        aria-hidden="true"
        className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

function NotificationsSection() {
  const [settings, setSettings] = useState({
    new_match: false,
    exchange_update: false,
    new_message: false,
    reviews: false,
  })
  const toggle = (key) => setSettings(prev => ({ ...prev, [key]: !prev[key] }))

  const items = [
    { key: 'new_match', label: 'Новые матчи', desc: 'Когда алгоритм находит подходящего партнёра' },
    { key: 'exchange_update', label: 'Обновления сделок', desc: 'Подтверждения начала и завершения обменов' },
    { key: 'new_message', label: 'Новые сообщения', desc: 'Входящие сообщения в чатах сделок' },
    { key: 'reviews', label: 'Отзывы', desc: 'Когда партнёр оставляет отзыв о сделке' },
  ]

  return (
    <div className="rounded-[40px] border border-white/5 bg-slate-900 p-8">
      <div className="mb-6 flex items-center gap-3">
        <h3 className="text-2xl font-black uppercase italic text-white">Уведомления</h3>
        <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-widest text-indigo-400">
          Coming soon
        </span>
      </div>
      <p className="mb-6 text-xs text-slate-500">Управление уведомлениями в приложении</p>
      <div className="max-w-md space-y-3">
        {items.map(({ key, label, desc }) => (
          <div key={key} className="flex items-center justify-between gap-4 rounded-2xl border border-white/5 bg-white/5 p-4">
            <div className="min-w-0">
              <p className="text-sm font-bold text-white">{label}</p>
              <p className="text-xs text-slate-500">{desc}</p>
            </div>
            <Toggle checked={settings[key]} onChange={() => toggle(key)} />
          </div>
        ))}
      </div>
    </div>
  )
}

function ProfilePage() {
  const { userId, email, logout } = useAuth()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [myListings, setMyListings] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingName, setEditingName] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [saveError, setSaveError] = useState(null)
  const [activeSection, setActiveSection] = useState('settings')
  const [receivedReviews, setReceivedReviews] = useState([])
  // listing_id → { open, interests, loading, error, accepting }
  const [interestState, setInterestState] = useState({})
  // Навыки пользователя
  const [mySkills, setMySkills] = useState({ offered: [], wanted: [] })

  useEffect(() => {
    if (!userId) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const [me, listings, userSkills, reviews] = await Promise.all([
          api.getMe(),
          api.listings({ author_id: userId }),
          api.getMySkills(),
          api.myReceivedReviews(),
        ])
        if (!cancelled) {
          setProfile(me)
          setMyListings(listings)
          setNameInput(me.full_name ?? '')
          setMySkills(userSkills)
          setReceivedReviews(reviews)
        }
      } catch {
        // профиль не загрузился — покажем онбординг
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [userId])

  const initials = initialsFromName(profile?.full_name, email)

  const handleUpdateProfile = async (payload) => {
    const updated = await api.updateMe(payload)
    setProfile(updated)
    setNameInput(updated.full_name ?? '')
    setEditingName(false)
  }

  const handleUpdateSkills = async (payload) => {
    await api.updateMySkills(payload)
    const updated = await api.getMySkills()
    setMySkills(updated)
  }

  const toggleInterests = async (listingId) => {
    const cur = interestState[listingId]
    // Если уже открыто — закрываем
    if (cur?.open) {
      setInterestState((prev) => ({ ...prev, [listingId]: { ...prev[listingId], open: false } }))
      return
    }
    // Открываем и загружаем
    setInterestState((prev) => ({
      ...prev,
      [listingId]: { open: true, interests: cur?.interests ?? [], loading: true, error: null, accepting: null },
    }))
    try {
      const data = await api.listingInterests(listingId)
      setInterestState((prev) => ({
        ...prev,
        [listingId]: { ...prev[listingId], interests: data, loading: false },
      }))
    } catch (e) {
      setInterestState((prev) => ({
        ...prev,
        [listingId]: { ...prev[listingId], loading: false, error: e.message },
      }))
    }
  }

  const handleAccept = async (listingId, responderId) => {
    setInterestState((prev) => ({ ...prev, [listingId]: { ...prev[listingId], accepting: responderId } }))
    try {
      await api.acceptInterest(listingId, responderId)
      // Перезагружаем отклики и объявления
      const [data, listings] = await Promise.all([
        api.listingInterests(listingId),
        api.listings({ author_id: userId }),
      ])
      setMyListings(listings)
      setInterestState((prev) => ({
        ...prev,
        [listingId]: { ...prev[listingId], interests: data, accepting: null },
      }))
    } catch (e) {
      setInterestState((prev) => ({
        ...prev,
        [listingId]: { ...prev[listingId], accepting: null, error: e.message },
      }))
    }
  }

  if (loading) {
    return (
      <div className="animate-page flex items-center justify-center py-20">
        <LoadingHint label="Загружаем профиль…" />
      </div>
    )
  }

  return (
    <div className="animate-page space-y-8">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        {/* ── Левая колонка ── */}
        <div className="space-y-6 lg:col-span-1">
          {/* Аккаунт */}
          <div className="rounded-[40px] border border-white/5 bg-slate-900 p-6">
            <h3 className="mb-3 text-sm font-black uppercase tracking-widest text-white">
              Аккаунт
            </h3>
            <p className="text-xs text-slate-500 break-all">{email}</p>
          </div>

          {/* Карточка профиля */}
          <div className="group relative overflow-hidden rounded-[40px] border border-white/5 bg-slate-900 p-8 text-center">
            <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-indigo-500 to-fuchsia-500" />
            <div className="mx-auto mb-6 flex size-24 rotate-3 items-center justify-center rounded-[32px] bg-indigo-600 text-3xl font-black text-white shadow-2xl transition-transform group-hover:rotate-0">
              {initials}
            </div>

            {editingName ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  void handleUpdateProfile({ full_name: nameInput.trim() || null })
                }}
                className="mb-4 flex flex-col gap-2"
              >
                <input
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-indigo-500"
                  placeholder="Ваше имя"
                />
                {saveError ? <p className="text-xs text-red-400">{saveError}</p> : null}
                <div className="flex gap-2">
                  <button
                    type="submit"
                    className="flex-1 rounded-xl bg-indigo-600 py-2 text-xs font-black text-white"
                  >
                    Сохранить
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingName(false)
                      setSaveError(null)
                    }}
                    className="flex-1 rounded-xl border border-white/10 py-2 text-xs text-slate-400"
                  >
                    Отмена
                  </button>
                </div>
              </form>
            ) : (
              <>
                <h3 className="text-xl font-black italic text-white">
                  {profile?.full_name ?? 'Без имени'}
                </h3>
                <p className="mt-1 text-xs font-bold uppercase tracking-widest text-slate-500">
                  {profile?.role ?? 'user'}
                </p>
              </>
            )}

            <div className="mt-8 space-y-4 border-t border-white/5 pt-8">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-black uppercase text-slate-400">Рейтинг</span>
                <span className="font-black text-indigo-400">
                  {profile?.rating ? `${Number(profile.rating).toFixed(2)} ★` : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-black uppercase text-slate-400">Объявлений</span>
                <span className="font-black text-white">{myListings.length}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setEditingName(true)}
              className="mt-8 w-full rounded-2xl border border-white/10 bg-white/5 py-3 text-[10px] font-black uppercase tracking-widest text-white transition hover:bg-white/10"
            >
              Редактировать
            </button>
          </div>

          {/* Меню */}
          <div className="space-y-2 rounded-[32px] border border-white/5 bg-slate-900 p-6">
            {[
              { key: 'settings', label: 'Настройки аккаунта', Icon: Settings },
              { key: 'security', label: 'Безопасность', Icon: ShieldCheck },
              { key: 'notifications', label: 'Уведомления', Icon: Bell },
            ].map(({ key, label, Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setActiveSection(key)}
                className={`flex w-full items-center space-x-3 rounded-xl p-3 transition ${
                  activeSection === key
                    ? 'border border-indigo-500/20 bg-indigo-600/10 text-indigo-400'
                    : 'text-slate-400 hover:bg-white/5'
                }`}
              >
                <Icon size={16} />
                <span className="text-xs font-bold">{label}</span>
              </button>
            ))}
            <button
              type="button"
              onClick={logout}
              className="mt-2 flex w-full items-center space-x-3 rounded-xl p-3 text-red-500 transition hover:bg-red-500/10"
            >
              <LogOut size={16} />
              <span className="text-xs font-bold">Выйти</span>
            </button>
          </div>
        </div>

        {/* ── Правая колонка ── */}
        <div className="space-y-8 lg:col-span-3">
          {activeSection === 'security' ? <SecuritySection /> : null}
          {activeSection === 'notifications' ? <NotificationsSection /> : null}
          {activeSection !== 'settings' ? null : <>
          {/* Мои навыки */}
          <div className="rounded-[40px] border border-white/5 bg-slate-900 p-8">
            <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h3 className="text-2xl font-black uppercase italic text-white">Мои навыки</h3>
                <p className="mt-2 text-xs font-medium text-slate-500">
                  Управляйте навыками для матчмейкинга.
                </p>
              </div>
            </div>

            <OnboardingBanner
              profile={profile}
              onSave={handleUpdateProfile}
              mySkills={mySkills}
              onSkillsSave={handleUpdateSkills}
            />
          </div>

          {/* Мои объявления */}
          <div className="rounded-[40px] border border-white/5 bg-slate-900 p-8">
            <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h3 className="text-2xl font-black uppercase italic text-white">
                  Мои объявления
                </h3>
                <p className="mt-2 text-xs font-medium text-slate-500">
                  Ваши активные предложения в сети.
                </p>
              </div>
              <button
                type="button"
                onClick={() => navigate('/deals', { state: { openCreate: true } })}
                className="rounded-xl bg-indigo-500 p-2 text-white transition hover:bg-indigo-400"
                aria-label="Добавить объявление"
              >
                <PlusCircle size={20} />
              </button>
            </div>

            {myListings.length > 0 ? (
              <ul className="space-y-3">
                {myListings.map((l) => {
                  const ist = interestState[l.id]
                  const pendingCount = ist?.interests?.filter((i) => i.status === 'pending').length ?? 0
                  return (
                    <li
                      key={l.id}
                      className="rounded-2xl border border-white/5 bg-white/5"
                    >
                      {/* Строка объявления */}
                      <div className="flex items-start justify-between gap-3 p-4">
                        <div className="min-w-0 flex-1 text-sm">
                          <p className="font-bold text-white">{l.title}</p>
                          <p className="mt-1 text-xs text-slate-400">
                            Предлагает: {l.offering_summary}
                          </p>
                          <p className="text-xs text-slate-400">Ищет: {l.seeking_summary}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => toggleInterests(l.id)}
                          className="flex shrink-0 items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-[10px] font-bold text-slate-300 transition hover:bg-white/10"
                        >
                          {pendingCount > 0 ? (
                            <span className="flex size-4 items-center justify-center rounded-full bg-indigo-600 text-[9px] font-black text-white">
                              {pendingCount}
                            </span>
                          ) : null}
                          Отклики
                          {ist?.open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                      </div>

                      {/* Список откликов */}
                      {ist?.open ? (
                        <div className="border-t border-white/5 px-4 pb-4 pt-3">
                          {ist.loading ? (
                            <LoadingHint label="Загружаем отклики…" />
                          ) : ist.error ? (
                            <p className="text-xs text-red-400">{ist.error}</p>
                          ) : ist.interests.length === 0 ? (
                            <p className="text-xs text-slate-500">Откликов пока нет.</p>
                          ) : (
                            <ul className="space-y-2">
                              {ist.interests.map((interest) => (
                                <li
                                  key={interest.id}
                                  className="flex items-start justify-between gap-3 rounded-xl border border-white/5 bg-black/20 p-3"
                                >
                                  <div className="min-w-0 flex-1">
                                    <p className="text-xs font-bold text-slate-300">
                                      Пользователь #{interest.responder_id}
                                    </p>
                                    {interest.message ? (
                                      <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                                        {interest.message}
                                      </p>
                                    ) : null}
                                    <span className={`mt-1 inline-block text-[9px] font-black uppercase tracking-widest ${
                                      interest.status === 'pending' ? 'text-amber-400' :
                                      interest.status === 'accepted' ? 'text-green-400' :
                                      'text-slate-500'
                                    }`}>
                                      {interest.status === 'pending' ? 'Ожидает' :
                                       interest.status === 'accepted' ? 'Принят' : 'Отклонён'}
                                    </span>
                                  </div>
                                  {interest.status === 'pending' ? (
                                    <div className="flex shrink-0 gap-2">
                                      <button
                                        type="button"
                                        onClick={() => handleAccept(l.id, interest.responder_id)}
                                        disabled={ist.accepting === interest.responder_id}
                                        className="flex items-center gap-1 rounded-lg bg-green-600/20 px-2.5 py-1.5 text-[10px] font-bold text-green-400 transition hover:bg-green-600/30 disabled:opacity-50"
                                      >
                                        <UserCheck size={12} />
                                        {ist.accepting === interest.responder_id ? '…' : 'Принять'}
                                      </button>
                                    </div>
                                  ) : null}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">
                У вас пока нет объявлений. Создайте первое на странице Сделки.
              </p>
            )}
          </div>

          {/* Trust Factors */}
          <div className="rounded-[40px] border border-white/5 bg-slate-900 p-8">
            <h3 className="mb-6 text-lg font-black uppercase italic text-white">Доверие</h3>
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="rounded-lg bg-green-500/10 p-2 text-green-400">
                    <CheckCircle2 size={16} />
                  </div>
                  <span className="text-sm font-bold text-slate-300">Аккаунт создан</span>
                </div>
                <span className="text-[10px] font-black text-green-500">OK</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div
                    className={`rounded-lg p-2 ${isProfileComplete(profile) ? 'bg-green-500/10 text-green-400' : 'bg-amber-500/10 text-amber-400'}`}
                  >
                    <Award size={16} />
                  </div>
                  <span className="text-sm font-bold text-slate-300">Профиль заполнен</span>
                </div>
                <span
                  className={`text-[10px] font-black ${isProfileComplete(profile) ? 'text-green-500' : 'text-amber-400'}`}
                >
                  {isProfileComplete(profile) ? 'OK' : 'ТРЕБУЕТСЯ'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="rounded-lg bg-slate-500/10 p-2 text-slate-400">
                    <Zap size={16} />
                  </div>
                  <span className="text-sm font-bold text-slate-300">Рейтинг матчинга</span>
                </div>
                <span className="text-[10px] font-black text-white">
                  {isProfileComplete(profile) ? 'Активен' : '-15% штраф'}
                </span>
              </div>
            </div>
          </div>
          {receivedReviews.length > 0 ? (
            <div className="rounded-[40px] border border-white/5 bg-slate-900 p-8">
              <h3 className="mb-6 text-lg font-black uppercase italic text-white">
                Отзывы обо мне
                <span className="ml-3 text-sm font-normal text-slate-500">({receivedReviews.length})</span>
              </h3>
              <div className="space-y-4">
                {receivedReviews.slice(0, 8).map((r) => (
                  <div key={r.id} className="rounded-2xl border border-white/5 bg-white/5 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-bold text-white">
                          {r.reviewer_name ?? `Пользователь #${r.reviewer_id}`}
                        </p>
                        {r.comment ? (
                          <p className="mt-1 text-xs text-slate-400">{r.comment}</p>
                        ) : null}
                      </div>
                      <span className="shrink-0 text-amber-400 text-sm">
                        {'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          </>}
        </div>
      </div>
    </div>
  )
}

export default ProfilePage
