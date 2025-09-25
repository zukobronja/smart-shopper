import React, { useEffect, useMemo, useState } from 'react';
import { Bell, ExternalLink, Pencil, Trash2, X } from 'lucide-react';
import { useFavorites, useFavoriteTags } from '../hooks/useFavorites';
import { useCurrentUser } from '../hooks/useCurrentUser';
import type { FavoriteProduct } from '../types/favorites';
import { fetchSearchRun } from '../services/search';
import type { SearchResponse } from '../types/search';

interface FavoriteCardProps {
  favorite: FavoriteProduct;
  onUpdate: (id: string, updates: any) => Promise<boolean>;
  onRemove: (id: string) => Promise<boolean>;
}

const FavoriteCard: React.FC<FavoriteCardProps> = ({ favorite, onUpdate, onRemove }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [notes, setNotes] = useState(favorite.notes || '');
  const [tags, setTags] = useState(favorite.tags.join(', '));
  const [priceAlert, setPriceAlert] = useState(favorite.price_alert_enabled);
  const [priceThreshold, setPriceThreshold] = useState(favorite.price_alert_threshold?.toString() || '');
  const [resolvedUrl, setResolvedUrl] = useState<string | null>(favorite.url ?? null);
  const [resolvingError, setResolvingError] = useState<string | null>(null);
  const [isResolving, setIsResolving] = useState(false);

  const handleSave = async () => {
    const success = await onUpdate(favorite.id, {
      notes: notes.trim() || undefined,
      tags: tags.split(',').map(t => t.trim()).filter(Boolean),
      price_alert_enabled: priceAlert,
      price_alert_threshold: priceThreshold ? parseFloat(priceThreshold) : undefined,
    });

    if (success) {
      setIsEditing(false);
    }
  };

  const handleCancel = () => {
    setNotes(favorite.notes || '');
    setTags(favorite.tags.join(', '));
    setPriceAlert(favorite.price_alert_enabled);
    setPriceThreshold(favorite.price_alert_threshold?.toString() || '');
    setIsEditing(false);
  };

  useEffect(() => {
    let ignore = false;

    const resolveSourceLink = async () => {
      if (favorite.url) {
        setResolvedUrl(favorite.url);
        setResolvingError(null);
        return;
      }

      if (!favorite.search_run_id) {
        setResolvedUrl(null);
        return;
      }

      setIsResolving(true);
      setResolvingError(null);

      try {
        const run: SearchResponse = await fetchSearchRun(favorite.search_run_id);
        if (ignore) {
          return;
        }
        const normalizedTitle = favorite.title?.trim().toLowerCase();
        const matched = run.results.find((result) =>
          result.title?.trim().toLowerCase() === normalizedTitle
        );
        const fallback = run.results[0];
        const resolved = matched?.url ?? fallback?.url ?? null;
        setResolvedUrl(resolved);
        setResolvingError(resolved ? null : 'Source unavailable');
      } catch (error) {
        if (!ignore) {
          setResolvingError(error instanceof Error ? error.message : 'Failed to resolve source');
          setResolvedUrl(null);
        }
      } finally {
        if (!ignore) {
          setIsResolving(false);
        }
      }
    };

    resolveSourceLink();

    return () => {
      ignore = true;
    };
  }, [favorite.url, favorite.search_run_id, favorite.title]);

  const sourceButtonLabel = useMemo(() => {
    if (isResolving) {
      return 'Resolving…';
    }
    if (resolvedUrl) {
      return 'View Source';
    }
    return 'Source unavailable';
  }, [isResolving, resolvedUrl]);

  return (
    <div className="glass-card favorite-card">
      <div className="favorite-card-header">
        <div>
          <h3 className="favorite-title">{favorite.title}</h3>
          {favorite.brand && <p className="favorite-brand">{favorite.brand}</p>}
        </div>
        <div className="favorite-actions">
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="action-button edit-button"
            title="Edit favorite"
            aria-label="Edit favorite"
          >
            <Pencil className="icon" aria-hidden="true" />
          </button>
          <button
            onClick={() => onRemove(favorite.id)}
            className="action-button remove-button"
            title="Remove from favorites"
            aria-label="Remove from favorites"
          >
            <Trash2 className="icon" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="favorite-details">
        {favorite.price && (
          <div className="price-info">
            <span className="price">
              {favorite.currency} {favorite.price.toFixed(2)}
            </span>
          </div>
        )}

        <div className="favorite-link">
          {resolvedUrl ? (
            <a
              href={resolvedUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="glass-button link-button"
            >
              <ExternalLink className="icon" aria-hidden="true" />
              <span>View Source</span>
            </a>
          ) : (
            <button
              type="button"
              className="glass-button link-button"
              disabled
              title={resolvingError ?? 'Source unavailable'}
            >
              <ExternalLink className="icon" aria-hidden="true" />
              <span>{sourceButtonLabel}</span>
            </button>
          )}
        </div>

        {favorite.tags.length > 0 && (
          <div className="favorite-tags">
            {favorite.tags.map((tag, index) => (
              <span key={index} className="tag">
                {tag}
              </span>
            ))}
          </div>
        )}

        {favorite.notes && (
          <div className="favorite-notes">
            <p>{favorite.notes}</p>
          </div>
        )}

        {favorite.price_alert_enabled && (
          <div className="price-alert-info">
            <Bell className="icon" aria-hidden="true" />
            <span>Price alert: {favorite.currency} {favorite.price_alert_threshold}</span>
          </div>
        )}
      </div>

      {isEditing && (
        <div className="favorite-edit-form">
          <div className="form-field">
            <label>Notes:</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add your notes about this product..."
              rows={3}
            />
          </div>

          <div className="form-field">
            <label>Tags (comma-separated):</label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="electronics, laptop, work"
            />
          </div>

          <div className="form-field">
            <label>
              <input
                type="checkbox"
                checked={priceAlert}
                onChange={(e) => setPriceAlert(e.target.checked)}
              />
              Enable price alerts
            </label>
          </div>

          {priceAlert && (
            <div className="form-field">
              <label>Alert when price drops below:</label>
              <input
                type="number"
                step="0.01"
                value={priceThreshold}
                onChange={(e) => setPriceThreshold(e.target.value)}
                placeholder="0.00"
              />
            </div>
          )}

          <div className="form-actions">
            <button onClick={handleSave} className="glass-button save-button">
              Save
            </button>
            <button onClick={handleCancel} className="glass-button cancel-button">
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="favorite-metadata">
        <small>
          Added {new Date(favorite.favorited_at).toLocaleDateString()}
          {favorite.original_search_query && (
            <> from search: "{favorite.original_search_query}"</>
          )}
        </small>
      </div>
    </div>
  );
};

export const FavoritesPage: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { user } = useCurrentUser();
  const [selectedTags, setSelectedTags] = useState<string>('');
  const [hasLoaded, setHasLoaded] = useState(false);
  
  const filters = React.useMemo(() => ({
    tags: selectedTags || undefined,
  }), [selectedTags]);
  
  const { favorites, loading, error, updateFavorite, removeFavorite, refetch } = useFavorites(filters);
  const { tags: availableTags } = useFavoriteTags();

  // Track when we've completed the first load
  React.useEffect(() => {
    if (!loading && !hasLoaded) {
      setHasLoaded(true);
    }
  }, [loading, hasLoaded]);

  const handleTagFilter = (tag: string) => {
    if (selectedTags === tag) {
      setSelectedTags('');
    } else {
      setSelectedTags(tag);
    }
  };

  if (!user) {
    return (
      <div className="favorites-page">
        <div className="favorites-header">
          <h2>Favorites</h2>
          <button onClick={onClose} className="close-button" aria-label="Close favorites">
            <X className="icon" aria-hidden="true" />
          </button>
        </div>
        <div className="auth-required">
          <p>Please sign in to view your favorites.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="favorites-page">
      <div className="favorites-header">
        <h2>My Favorites ({favorites.length})</h2>
        <button onClick={onClose} className="close-button" aria-label="Close favorites">
          <X className="icon" aria-hidden="true" />
        </button>
      </div>

      {availableTags.length > 0 && (
        <div className="tag-filters">
          <h3>Filter by tags:</h3>
          <div className="tag-list">
            <button
              onClick={() => setSelectedTags('')}
              className={`tag-filter ${selectedTags === '' ? 'active' : ''}`}
            >
              All
            </button>
            {availableTags.map((tag) => (
              <button
                key={tag}
                onClick={() => handleTagFilter(tag)}
                className={`tag-filter ${selectedTags === tag ? 'active' : ''}`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && !hasLoaded && (
        <div className="loading-state">
          <p>Loading favorites...</p>
        </div>
      )}

      {error && (
        <div className="error-state">
          <p>Error: {error}</p>
          <button onClick={refetch} className="glass-button">
            Retry
          </button>
        </div>
      )}

      {hasLoaded && !error && favorites.length === 0 && (
        <div className="empty-state">
          <p>No favorites yet.</p>
          <p>Start by adding products to your favorites during search!</p>
        </div>
      )}

      {hasLoaded && !error && favorites.length > 0 && (
        <div className="favorites-grid">
          {loading && (
            <div className="favorites-loading-overlay">
              <p>Updating...</p>
            </div>
          )}
          {favorites.map((favorite) => (
            <FavoriteCard
              key={favorite.id}
              favorite={favorite}
              onUpdate={updateFavorite}
              onRemove={removeFavorite}
            />
          ))}
        </div>
      )}
    </div>
  );
};
