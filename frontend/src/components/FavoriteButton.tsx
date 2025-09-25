import React, { useState } from 'react';
import { Heart, HeartOff, Loader2 } from 'lucide-react';
import { useFavorites } from '../hooks/useFavorites';
import { useCurrentUser } from '../hooks/useCurrentUser';
import type { ProductResult } from '../types/search';

interface FavoriteButtonProps {
  product: ProductResult;
  searchQuery?: string;
  searchRunId?: string;
  onAuthRequired?: () => void;
  className?: string;
}

export const FavoriteButton: React.FC<FavoriteButtonProps> = ({
  product,
  searchQuery,
  searchRunId,
  onAuthRequired,
  className = '',
}) => {
  const { user } = useCurrentUser();
  const { addFavorite, removeFavorite, isFavorited, getFavoriteId } = useFavorites();
  const [isProcessing, setIsProcessing] = useState(false);

  const isCurrentlyFavorited = isFavorited(product.url, product.title);
  const favoriteId = getFavoriteId(product.url, product.title);

  const handleToggleFavorite = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!user) {
      onAuthRequired?.();
      return;
    }

    setIsProcessing(true);

    try {
      if (isCurrentlyFavorited && favoriteId) {
        await removeFavorite(favoriteId);
      } else {
        await addFavorite({
          title: product.title || "",
          brand: product.brand || undefined,
          url: product.url || undefined,
          domain: product.domain || undefined,
          price: typeof product.price === 'number' ? product.price : undefined,
          currency: product.currency || "USD",
          image_url: undefined, // We don't have image URLs in search results yet
          specs: (product.specs && typeof product.specs === 'object') ? product.specs : {},
          description: product.explanation || undefined,
          original_search_query: searchQuery || undefined,
          search_run_id: searchRunId || undefined,
          notes: undefined,
          tags: [],
          price_alert_enabled: false,
          price_alert_threshold: undefined,
          availability_alert_enabled: false,
        });
      }
    } catch (error) {
      console.error('Failed to toggle favorite:', error);
      // Log the product data to help debug validation issues
      console.error('Product data:', product);
      // Log the data we're trying to send
      console.error('Favorite data being sent:', {
        title: product.title || "",
        brand: product.brand || undefined,
        url: product.url || undefined,
        domain: product.domain || undefined,
        price: typeof product.price === 'number' ? product.price : undefined,
        currency: product.currency || "USD",
        image_url: undefined,
        specs: (product.specs && typeof product.specs === 'object') ? product.specs : {},
        description: product.explanation || undefined,
        original_search_query: searchQuery || undefined,
        search_run_id: searchRunId || undefined,
        notes: undefined,
        tags: [],
        price_alert_enabled: false,
        price_alert_threshold: undefined,
        availability_alert_enabled: false,
      });
      // Log the full error response if available
      if (error && typeof error === 'object' && 'response' in error) {
        console.error('Error response:', (error as any).response);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleToggleFavorite}
      disabled={isProcessing}
      className={`favorite-button ${isCurrentlyFavorited ? 'favorited' : 'not-favorited'} ${className}`}
      title={isCurrentlyFavorited ? 'Remove from favorites' : 'Add to favorites'}
      aria-label={isCurrentlyFavorited ? 'Remove from favorites' : 'Add to favorites'}
    >
      {isProcessing ? (
        <Loader2 className="icon icon-spinner" aria-hidden="true" />
      ) : isCurrentlyFavorited ? (
        <Heart className="icon icon-filled" aria-hidden="true" />
      ) : (
        <HeartOff className="icon" aria-hidden="true" />
      )}
    </button>
  );
};
