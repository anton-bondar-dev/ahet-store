export function CommentsTab() {
  return (
    <div>
      <h2 className="mb-5 text-lg font-semibold text-gray-900">Мої коментарі</h2>
      <div className="flex flex-col items-center rounded-lg border border-dashed border-gray-300 p-12 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 text-3xl">
          💬
        </div>
        <p className="max-w-sm text-gray-500">
          Ви ще не залишили жодного коментаря. Ця функція з'явиться у майбутніх
          оновленнях!
        </p>
      </div>
    </div>
  )
}
