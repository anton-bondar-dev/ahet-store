import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  getListMacrosQueryKey,
  useCreateMacro,
  useDeleteMacro,
  useListMacros,
  useUpdateMacro,
} from '../../api/generated/support/support'
import type { MacroOut } from '../../api/generated/onlineStoreAPI.schemas'

// CRUD for reply templates. Content may contain {first_name}, {last_name},
// {username} — resolved server-side when inserted into a specific chat.
export function MacrosTab() {
  const queryClient = useQueryClient()
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: getListMacrosQueryKey() })

  const { data, isLoading } = useListMacros()
  const macros = data?.data ?? []
  const create = useCreateMacro({ mutation: { onSuccess: invalidate } })
  const del = useDeleteMacro({ mutation: { onSuccess: invalidate } })

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  const add = async () => {
    if (!title.trim() || !content.trim() || create.isPending) return
    await create.mutateAsync({ data: { title: title.trim(), content } }).catch(() => {})
    setTitle('')
    setContent('')
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Create */}
      <div className="rounded-lg border border-gray-200 p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Новий макрос</h3>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Назва"
          className="mb-2 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
        />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={4}
          placeholder="Текст. Змінні: {first_name}, {username}"
          className="mb-2 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
        />
        <button
          type="button"
          onClick={add}
          disabled={!title.trim() || !content.trim() || create.isPending}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:opacity-60"
        >
          Додати
        </button>
      </div>

      {/* List */}
      <div>
        {isLoading ? (
          <p className="text-sm text-gray-400">Завантаження…</p>
        ) : macros.length === 0 ? (
          <p className="text-sm text-gray-400">Ще немає макросів</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {macros.map((m) => (
              <MacroRow key={m.id} macro={m} onChanged={invalidate} onDelete={() => del.mutate({ macroId: m.id })} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function MacroRow({
  macro,
  onChanged,
  onDelete,
}: {
  macro: MacroOut
  onChanged: () => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(macro.title)
  const [content, setContent] = useState(macro.content)
  const update = useUpdateMacro({ mutation: { onSuccess: () => { onChanged(); setEditing(false) } } })

  if (editing) {
    return (
      <li className="rounded-lg border border-gray-200 p-3">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mb-2 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none"
        />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
          className="mb-2 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none"
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => update.mutate({ macroId: macro.id, data: { title, content } })}
            className="rounded-md bg-gray-900 px-3 py-1 text-xs font-semibold text-white hover:bg-gray-700"
          >
            Зберегти
          </button>
          <button type="button" onClick={() => setEditing(false)} className="text-xs text-gray-500">
            Скасувати
          </button>
        </div>
      </li>
    )
  }

  return (
    <li className="rounded-lg border border-gray-200 p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-gray-900">{macro.title}</p>
        <div className="flex shrink-0 gap-2 text-xs">
          <button type="button" onClick={() => setEditing(true)} className="text-gray-500 hover:text-gray-900">
            Змінити
          </button>
          <button type="button" onClick={onDelete} className="text-red-600 hover:text-red-800">
            Видалити
          </button>
        </div>
      </div>
      <p className="mt-1 whitespace-pre-wrap text-sm text-gray-600">{macro.content}</p>
    </li>
  )
}
