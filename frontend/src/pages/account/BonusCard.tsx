// Bonuses lighten the card toward white, up to this cap.
const MAX_BONUS = 1000

export function BonusCard({ balance }: { balance: number }) {
  const t = Math.min(Math.max(balance, 0) / MAX_BONUS, 1)
  // Whiten with bonuses: raise lightness, drop saturation as t → 1.
  const light = 32 + t * 53 // 32%..85%
  const sat = 72 - t * 28 // 72%..44%
  const top = `hsl(0, ${sat}%, ${Math.min(light + 6, 92)}%)`
  const bottom = `hsl(0, ${sat}%, ${Math.max(light - 12, 22)}%)`
  const isLight = light > 62
  const stripe = isLight ? '#7f1d1d' : '#ffffff'

  return (
    <div
      className={`relative overflow-hidden rounded-xl p-5 shadow-sm ${
        isLight ? 'text-red-950' : 'text-white'
      }`}
      style={{ backgroundImage: `linear-gradient(to bottom right, ${top}, ${bottom})` }}
    >
      {/* Decorative diagonal-stripe pattern overlay. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-15"
        style={{
          backgroundImage: `repeating-linear-gradient(45deg, ${stripe} 0, ${stripe} 2px, transparent 2px, transparent 12px)`,
        }}
      />
      <div className="relative">
        <p className="text-sm font-medium opacity-90">Ваш бонусний баланс</p>
        <p className="mt-1 text-3xl font-bold">{balance}</p>
        {balance === 0 && (
          <p className="mt-1 text-xs opacity-80">Нараховується при покупках</p>
        )}
      </div>
    </div>
  )
}
