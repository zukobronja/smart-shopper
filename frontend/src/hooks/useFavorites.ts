import { useState, useEffect, useCallback } from 'react';
import { FavoritesService } from '../services/favorites';
import type { 
  FavoriteProduct, 
  FavoriteProductCreate, 
  FavoriteProductUpdate, 
  FavoritesFilters 
} from '../types/favorites';
import { useCurrentUser } from './useCurrentUser';

export const useFavorites = (filters?: FavoritesFilters) => {
  const [favorites, setFavorites] = useState<FavoriteProduct[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user } = useCurrentUser();

  const loadFavorites = useCallback(async () => {
    if (!user) {
      setFavorites([]);
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      const result = await FavoritesService.getFavorites(filters);
      setFavorites(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load favorites');
      setFavorites([]);
    } finally {
      setLoading(false);
    }
  }, [user, JSON.stringify(filters)]);

  useEffect(() => {
    loadFavorites();
  }, [loadFavorites]);

  const addFavorite = useCallback(async (data: FavoriteProductCreate): Promise<boolean> => {
    if (!user) return false;

    try {
      const newFavorite = await FavoritesService.addFavorite(data);
      setFavorites(prev => [newFavorite, ...prev]);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add favorite');
      return false;
    }
  }, [user]);

  const updateFavorite = useCallback(async (id: string, data: FavoriteProductUpdate): Promise<boolean> => {
    try {
      const updatedFavorite = await FavoritesService.updateFavorite(id, data);
      setFavorites(prev => prev.map(fav => fav.id === id ? updatedFavorite : fav));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update favorite');
      return false;
    }
  }, []);

  const removeFavorite = useCallback(async (id: string): Promise<boolean> => {
    try {
      await FavoritesService.removeFavorite(id);
      setFavorites(prev => prev.filter(fav => fav.id !== id));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove favorite');
      return false;
    }
  }, []);

  const isFavorited = useCallback((productUrl?: string, productTitle?: string) => {
    if (!productUrl && !productTitle) return false;
    
    return favorites.some(fav => {
      if (productUrl && fav.url) {
        return fav.url === productUrl;
      }
      return fav.title === productTitle;
    });
  }, [favorites]);

  const getFavoriteId = useCallback((productUrl?: string, productTitle?: string) => {
    if (!productUrl && !productTitle) return null;
    
    const favorite = favorites.find(fav => {
      if (productUrl && fav.url) {
        return fav.url === productUrl;
      }
      return fav.title === productTitle;
    });
    
    return favorite?.id || null;
  }, [favorites]);

  return {
    favorites,
    loading,
    error,
    addFavorite,
    updateFavorite,
    removeFavorite,
    isFavorited,
    getFavoriteId,
    refetch: loadFavorites,
  };
};

export const useFavoriteTags = () => {
  const [tags, setTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user } = useCurrentUser();

  const loadTags = useCallback(async () => {
    if (!user) {
      setTags([]);
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      const result = await FavoritesService.getFavoriteTags();
      setTags(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tags');
      setTags([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadTags();
  }, [loadTags]);

  return {
    tags,
    loading,
    error,
    refetch: loadTags,
  };
};