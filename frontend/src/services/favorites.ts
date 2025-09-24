import { buildUrl } from './http';
import type { 
  FavoriteProduct, 
  FavoriteProductCreate, 
  FavoriteProductUpdate, 
  FavoritesFilters 
} from '../types/favorites';

async function fetchWithCredentials<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage: string;
    
    try {
      const errorData = JSON.parse(errorText);
      errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
    } catch {
      errorMessage = errorText || `HTTP ${response.status}`;
    }
    
    throw new Error(errorMessage);
  }

  if (response.status === 204) {
    return undefined as any;
  }

  return response.json() as Promise<T>;
}

export class FavoritesService {
  private static readonly BASE_URL = '/v1/favorites';

  /**
   * Get user's favorite products
   */
  static async getFavorites(filters?: FavoritesFilters): Promise<FavoriteProduct[]> {
    const params = new URLSearchParams();
    
    if (filters?.limit) {
      params.append('limit', filters.limit.toString());
    }
    if (filters?.skip) {
      params.append('skip', filters.skip.toString());
    }
    if (filters?.tags) {
      params.append('tags', filters.tags);
    }

    const url = buildUrl(`${this.BASE_URL}${params.toString() ? `?${params.toString()}` : ''}`);
    return fetchWithCredentials<FavoriteProduct[]>(url);
  }

  /**
   * Add a product to favorites
   */
  static async addFavorite(data: FavoriteProductCreate): Promise<FavoriteProduct> {
    const url = buildUrl(this.BASE_URL);
    return fetchWithCredentials<FavoriteProduct>(url, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * Get a specific favorite by ID
   */
  static async getFavorite(id: string): Promise<FavoriteProduct> {
    const url = buildUrl(`${this.BASE_URL}/${id}`);
    return fetchWithCredentials<FavoriteProduct>(url);
  }

  /**
   * Update a favorite product
   */
  static async updateFavorite(id: string, data: FavoriteProductUpdate): Promise<FavoriteProduct> {
    const url = buildUrl(`${this.BASE_URL}/${id}`);
    return fetchWithCredentials<FavoriteProduct>(url, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  /**
   * Remove a product from favorites
   */
  static async removeFavorite(id: string): Promise<void> {
    const url = buildUrl(`${this.BASE_URL}/${id}`);
    return fetchWithCredentials<void>(url, {
      method: 'DELETE',
    });
  }

  /**
   * Check if a product (by URL) is favorited
   */
  static async checkFavoriteStatus(urlHash: string): Promise<{ is_favorited: boolean; favorite_id?: string }> {
    const url = buildUrl(`${this.BASE_URL}/check/${encodeURIComponent(urlHash)}`);
    return fetchWithCredentials<{ is_favorited: boolean; favorite_id?: string }>(url);
  }

  /**
   * Get all unique tags used in user's favorites
   */
  static async getFavoriteTags(): Promise<string[]> {
    const url = buildUrl(`${this.BASE_URL}/tags`);
    return fetchWithCredentials<string[]>(url);
  }
}