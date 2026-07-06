import axios from 'axios';

// Single source of truth for the backend origin.
export const API_BASE_URL = 'http://127.0.0.1:8000';

// The Orval-generated client calls the global axios instance with relative
// paths (e.g. `/api/catalog/products`), so we set the backend origin here once.
axios.defaults.baseURL = API_BASE_URL;

// Build an absolute URL for a media path returned by the API
// (e.g. "/media/products/images/x.jpg"). Returns null when there's no image.
export function productImageUrl(image: string | null): string | null {
  if (!image) return null;
  return image.startsWith('http') ? image : `${API_BASE_URL}${image}`;
}
