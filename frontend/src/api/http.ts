import axios from 'axios';

// The Orval-generated client calls the global axios instance with relative
// paths (e.g. `/api/catalog/products`), so we set the backend origin here once.
axios.defaults.baseURL = 'http://127.0.0.1:8000';
