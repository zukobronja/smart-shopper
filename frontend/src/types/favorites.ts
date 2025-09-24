export interface FavoriteProduct {
  id: string;
  title: string;
  brand?: string;
  url?: string;
  domain?: string;
  price?: number;
  currency: string;
  image_url?: string;
  specs: Record<string, any>;
  description?: string;
  original_search_query?: string;
  search_run_id?: string;
  notes?: string;
  tags: string[];
  price_alert_enabled: boolean;
  price_alert_threshold?: number;
  availability_alert_enabled: boolean;
  favorited_at: string;
  last_checked?: string;
  is_available?: boolean;
}

export interface FavoriteProductCreate {
  title: string;
  brand?: string;
  url?: string;
  domain?: string;
  price?: number;
  currency?: string;
  image_url?: string;
  specs?: Record<string, any>;
  description?: string;
  original_search_query?: string;
  search_run_id?: string;
  notes?: string;
  tags?: string[];
  price_alert_enabled?: boolean;
  price_alert_threshold?: number;
  availability_alert_enabled?: boolean;
}

export interface FavoriteProductUpdate {
  notes?: string;
  tags?: string[];
  price_alert_enabled?: boolean;
  price_alert_threshold?: number;
  availability_alert_enabled?: boolean;
}

export interface FavoritesFilters {
  tags?: string;
  limit?: number;
  skip?: number;
}