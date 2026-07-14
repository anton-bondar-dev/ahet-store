// Google Sign-In client id. Public value; provided at build/dev time via a
// Vite env var (put it in frontend/.env.local). Empty → the Google button
// simply doesn't render.
export const GOOGLE_CLIENT_ID: string =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''
