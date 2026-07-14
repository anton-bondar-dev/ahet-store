const FLOW: { key: string; label: string }[] = [
  { key: 'new', label: 'Нове' },
  { key: 'processing', label: 'Обробка' },
  { key: 'shipped', label: 'Відправлено' },
  { key: 'delivered', label: 'Доставлено' },
]

export function StatusStepper({ status }: { status: string }) {
  if (status === 'cancelled') {
    return (
      <span className="inline-flex w-fit items-center rounded-full bg-red-50 px-3 py-1 text-sm font-medium text-red-700">
        Скасовано
      </span>
    )
  }

  const activeIndex = Math.max(
    0,
    FLOW.findIndex((s) => s.key === status),
  )

  return (
    <div className="flex items-center">
      {FLOW.map((stage, i) => {
        const done = i < activeIndex
        const active = i === activeIndex
        return (
          <div key={stage.key} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold ${
                  done
                    ? 'border-green-600 bg-green-600 text-white'
                    : active
                      ? 'border-gray-900 bg-gray-900 text-white'
                      : 'border-gray-300 text-gray-400'
                }`}
              >
                {done ? '✓' : i + 1}
              </span>
              <span
                className={`mt-1 whitespace-nowrap text-[11px] ${
                  active ? 'font-semibold text-gray-900' : 'text-gray-500'
                }`}
              >
                {stage.label}
              </span>
            </div>
            {i < FLOW.length - 1 && (
              <span
                className={`mx-1 h-px flex-1 ${i < activeIndex ? 'bg-green-600' : 'bg-gray-200'}`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
