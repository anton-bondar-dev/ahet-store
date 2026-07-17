import { useState, type InputHTMLAttributes } from 'react'

// A password field with a show/hide (eye) toggle that turns the dots into
// readable letters. Drop-in for any <input type="password">; forwards all the
// usual props (value, onChange, placeholder, required, autoComplete, …).
export function PasswordInput({
  className = '',
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? 'text' : 'password'}
        className={`w-full rounded-md border border-gray-300 py-2 pl-3 pr-10 text-sm text-gray-900 focus:border-brand focus:outline-none ${className}`}
      />
      <button
        type="button"
        // Not part of the tab order — it's an assist, not a form control.
        tabIndex={-1}
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Сховати пароль' : 'Показати пароль'}
        title={visible ? 'Сховати пароль' : 'Показати пароль'}
        aria-pressed={visible}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 transition hover:text-brand"
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  )
}

function EyeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function EyeOffIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 7 10 7a13.2 13.2 0 0 1-1.67 2.68M6.06 6.06A13.4 13.4 0 0 0 2 12s3.5 7 10 7a9.1 9.1 0 0 0 5.94-2.06M9.9 9.9a3 3 0 0 0 4.2 4.2" />
      <path d="M2 2l20 20" />
    </svg>
  )
}
