import React, { useEffect, useRef, useState } from "react";
import { Heart } from "lucide-react";
import "./App.css";
import { searchProducts } from "./services/search";
import { fetchGoogleAuthorizationUrl } from "./services/auth";
import { useCurrentUser } from "./hooks/useCurrentUser";
import { ProductResult, SearchResponse } from "./types/search";
import { FavoriteButton } from "./components/FavoriteButton";
import { FavoritesPage } from "./components/FavoritesPage";

// Smart price detection utility
interface PriceDetection {
  amount: number | null;
  currency: string | null;
  cleanQuery: string;
}

function detectPriceFromQuery(query: string): PriceDetection {
  const result: PriceDetection = {
    amount: null,
    currency: null,
    cleanQuery: query
  };

  // Currency symbols and codes with their standardized forms
  const currencyPatterns = [
    { regex: /\$(\d+(?:,\d{3})*(?:\.\d{2})?)/gi, currency: 'USD', symbol: '$' },
    { regex: /€(\d+(?:,\d{3})*(?:\.\d{2})?)/gi, currency: 'EUR', symbol: '€' },
    { regex: /£(\d+(?:,\d{3})*(?:\.\d{2})?)/gi, currency: 'GBP', symbol: '£' },
    { regex: /¥(\d+(?:,\d{3})*(?:\.\d{2})?)/gi, currency: 'JPY', symbol: '¥' },
    { regex: /₹(\d+(?:,\d{3})*(?:\.\d{2})?)/gi, currency: 'INR', symbol: '₹' },
    { regex: /₪(\d+(?:,\d{3})*(?:\.\d{2})?)/gi, currency: 'ILS', symbol: '₪' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:usd|dollars?))/gi, currency: 'USD', symbol: '$' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:eur|euros?))/gi, currency: 'EUR', symbol: '€' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:gbp|pounds?))/gi, currency: 'GBP', symbol: '£' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:aed|dirhams?))/gi, currency: 'AED', symbol: 'د.إ' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:jpy|yen))/gi, currency: 'JPY', symbol: '¥' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:inr|rupees?))/gi, currency: 'INR', symbol: '₹' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:cad|canadian))/gi, currency: 'CAD', symbol: 'C$' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:aud|australian))/gi, currency: 'AUD', symbol: 'A$' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:chf|swiss))/gi, currency: 'CHF', symbol: '₣' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:cny|yuan|rmb))/gi, currency: 'CNY', symbol: '¥' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:krw|won))/gi, currency: 'KRW', symbol: '₩' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:sgd|singapore))/gi, currency: 'SGD', symbol: 'S$' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:hkd|hong\s*kong))/gi, currency: 'HKD', symbol: 'HK$' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:nzd|new\s*zealand))/gi, currency: 'NZD', symbol: 'NZ$' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:sek|krona))/gi, currency: 'SEK', symbol: 'kr' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:nok|norwegian))/gi, currency: 'NOK', symbol: 'kr' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dkk|danish))/gi, currency: 'DKK', symbol: 'kr' },
    { regex: /(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:ils|shekel|shekels))/gi, currency: 'ILS', symbol: '₪' },
  ];

  // "under X", "below X", "less than X", "max X" patterns
  const pricePatterns = [
    /(?:under|below|less\s+than|max|maximum|up\s+to)\s+[\$€£¥₹₪]?(\d+(?:,\d{3})*(?:\.\d{2})?)/gi,
    /[\$€£¥₹₪]?(\d+(?:,\d{3})*(?:\.\d{2})?)\s+(?:or\s+)?(?:less|max|maximum)/gi,
    /budget\s+(?:of\s+)?[\$€£¥₹₪]?(\d+(?:,\d{3})*(?:\.\d{2})?)/gi,
  ];

  let cleanQuery = query;

  // First, try to find currency-specific patterns
  for (const pattern of currencyPatterns) {
    const match = pattern.regex.exec(query);
    if (match) {
      const amountStr = match[1].replace(/[^\d.]/g, ''); // Remove commas and currency text
      const amount = parseFloat(amountStr);
      if (amount > 0) {
        result.amount = amount;
        result.currency = pattern.currency;
        // Remove the matched text from query
        cleanQuery = query.replace(pattern.regex, '').trim();
        break;
      }
    }
  }

  // If no currency-specific pattern found, try general price patterns
  if (result.amount === null) {
    for (const pattern of pricePatterns) {
      const match = pattern.exec(query);
      if (match) {
        const amountStr = match[1].replace(/,/g, ''); // Remove commas
        const amount = parseFloat(amountStr);
        if (amount > 0) {
          result.amount = amount;
          // Try to detect currency from context
          if (query.includes('$') || /usd|dollar/i.test(query)) {
            result.currency = 'USD';
          } else if (query.includes('€') || /eur|euro/i.test(query)) {
            result.currency = 'EUR';
          } else if (query.includes('£') || /gbp|pound/i.test(query)) {
            result.currency = 'GBP';
          } else if (/aed|dirham/i.test(query)) {
            result.currency = 'AED';
          } else if (/jpy|yen/i.test(query)) {
            result.currency = 'JPY';
          } else if (/inr|rupee/i.test(query)) {
            result.currency = 'INR';
          } else if (/ils|shekel/i.test(query)) {
            result.currency = 'ILS';
          }
          // Remove the matched price text from query
          cleanQuery = query.replace(pattern, '').trim();
          break;
        }
      }
    }
  }

  // Clean up the query by removing extra spaces and common price-related words
  cleanQuery = cleanQuery
    .replace(/\s+/g, ' ')
    .replace(/\b(?:under|below|less\s+than|max|maximum|up\s+to|budget|or\s+less)\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim();

  result.cleanQuery = cleanQuery;
  return result;
}

// Currency symbol helper
function getCurrencySymbol(currency: string): string {
  const symbols: Record<string, string> = {
    'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CNY': '¥', 'INR': '₹',
    'CAD': 'C$', 'AUD': 'A$', 'NZD': 'NZ$', 'KRW': '₩', 'AED': 'د.إ',
    'CHF': '₣', 'SGD': 'S$', 'HKD': 'HK$', 'SEK': 'kr', 'NOK': 'kr', 'DKK': 'kr',
    'RUB': '₽', 'BRL': 'R$', 'MXN': '$', 'ZAR': 'R', 'THB': '฿', 'TRY': '₺',
    'PLN': 'zł', 'CZK': 'Kč', 'HUF': 'Ft', 'ILS': '₪', 'MYR': 'RM', 'PHP': '₱',
    'IDR': 'Rp', 'VND': '₫', 'TWD': 'NT$', 'EGP': 'E£', 'SAR': 'ر.س', 'QAR': 'ر.ق',
    'KWD': 'د.ك', 'BHD': 'د.ب', 'OMR': 'ر.ع.', 'JOD': 'د.أ', 'LBP': 'ل.ل',
  };
  return symbols[currency] || currency;
}

// Browser locale detection for currency
function getDefaultCurrency(): string {
  try {
    const locale = navigator.language || 'en-US';
    
    // Common locale to currency mappings
    const localeToCurrency: Record<string, string> = {
      'en-US': 'USD', 'en-CA': 'CAD', 'en-AU': 'AUD', 'en-NZ': 'NZD',
      'en-GB': 'GBP', 'en-IE': 'EUR', 'en-IN': 'INR', 'en-SG': 'SGD', 'en-HK': 'HKD',
      'de': 'EUR', 'de-DE': 'EUR', 'fr': 'EUR', 'fr-FR': 'EUR', 'fr-CA': 'CAD',
      'es': 'EUR', 'es-ES': 'EUR', 'es-MX': 'MXN', 'it': 'EUR', 'it-IT': 'EUR',
      'nl': 'EUR', 'nl-NL': 'EUR', 'pt': 'EUR', 'pt-PT': 'EUR', 'pt-BR': 'BRL',
      'ja': 'JPY', 'ja-JP': 'JPY', 'zh': 'CNY', 'zh-CN': 'CNY', 'zh-TW': 'TWD',
      'ko': 'KRW', 'ko-KR': 'KRW', 'hi': 'INR', 'hi-IN': 'INR',
      'ar': 'AED', 'ar-AE': 'AED', 'ar-SA': 'SAR', 'ar-EG': 'EGP',
      'ru': 'RUB', 'ru-RU': 'RUB', 'th': 'THB', 'th-TH': 'THB',
      'tr': 'TRY', 'tr-TR': 'TRY', 'pl': 'PLN', 'pl-PL': 'PLN',
      'cs': 'CZK', 'cs-CZ': 'CZK', 'hu': 'HUF', 'hu-HU': 'HUF',
      'sv': 'SEK', 'sv-SE': 'SEK', 'no': 'NOK', 'no-NO': 'NOK',
      'da': 'DKK', 'da-DK': 'DKK', 'he': 'ILS', 'he-IL': 'ILS',
    };

    // Try exact match first
    if (localeToCurrency[locale]) {
      return localeToCurrency[locale];
    }

    // Try language code only
    const langCode = locale.split('-')[0];
    if (localeToCurrency[langCode]) {
      return localeToCurrency[langCode];
    }

    // Default fallback
    return 'USD';
  } catch {
    return 'USD';
  }
}

// Comprehensive currency list
const CURRENCIES = [
  { code: 'USD', name: 'US Dollar', symbol: '$' },
  { code: 'EUR', name: 'Euro', symbol: '€' },
  { code: 'GBP', name: 'British Pound', symbol: '£' },
  { code: 'AED', name: 'UAE Dirham', symbol: 'د.إ' },
  { code: 'JPY', name: 'Japanese Yen', symbol: '¥' },
  { code: 'CNY', name: 'Chinese Yuan', symbol: '¥' },
  { code: 'INR', name: 'Indian Rupee', symbol: '₹' },
  { code: 'CAD', name: 'Canadian Dollar', symbol: 'C$' },
  { code: 'AUD', name: 'Australian Dollar', symbol: 'A$' },
  { code: 'CHF', name: 'Swiss Franc', symbol: '₣' },
  { code: 'SGD', name: 'Singapore Dollar', symbol: 'S$' },
  { code: 'HKD', name: 'Hong Kong Dollar', symbol: 'HK$' },
  { code: 'NZD', name: 'New Zealand Dollar', symbol: 'NZ$' },
  { code: 'SEK', name: 'Swedish Krona', symbol: 'kr' },
  { code: 'NOK', name: 'Norwegian Krone', symbol: 'kr' },
  { code: 'DKK', name: 'Danish Krone', symbol: 'kr' },
  { code: 'KRW', name: 'South Korean Won', symbol: '₩' },
  { code: 'RUB', name: 'Russian Ruble', symbol: '₽' },
  { code: 'BRL', name: 'Brazilian Real', symbol: 'R$' },
  { code: 'MXN', name: 'Mexican Peso', symbol: '$' },
  { code: 'ZAR', name: 'South African Rand', symbol: 'R' },
  { code: 'THB', name: 'Thai Baht', symbol: '฿' },
  { code: 'TRY', name: 'Turkish Lira', symbol: '₺' },
  { code: 'PLN', name: 'Polish Zloty', symbol: 'zł' },
  { code: 'CZK', name: 'Czech Koruna', symbol: 'Kč' },
  { code: 'HUF', name: 'Hungarian Forint', symbol: 'Ft' },
  { code: 'ILS', name: 'Israeli Shekel', symbol: '₪' },
  { code: 'MYR', name: 'Malaysian Ringgit', symbol: 'RM' },
  { code: 'PHP', name: 'Philippine Peso', symbol: '₱' },
  { code: 'IDR', name: 'Indonesian Rupiah', symbol: 'Rp' },
  { code: 'VND', name: 'Vietnamese Dong', symbol: '₫' },
  { code: 'TWD', name: 'Taiwan Dollar', symbol: 'NT$' },
  { code: 'EGP', name: 'Egyptian Pound', symbol: 'E£' },
  { code: 'SAR', name: 'Saudi Riyal', symbol: 'ر.س' },
  { code: 'QAR', name: 'Qatari Riyal', symbol: 'ر.ق' },
  { code: 'KWD', name: 'Kuwaiti Dinar', symbol: 'د.ك' },
  { code: 'BHD', name: 'Bahraini Dinar', symbol: 'د.ب' },
  { code: 'OMR', name: 'Omani Rial', symbol: 'ر.ع.' },
  { code: 'JOD', name: 'Jordanian Dinar', symbol: 'د.أ' },
];

// SmartShopper brand colors
const brand = {
  teal: "#1AB6B2",
  indigo: "#02de91d0",
};

interface SearchHistoryItem {
  query: string;
  runId: string;
  timestamp: string;
  topTitle?: string;
  totalTimeMs: number;
  coverageScore: number;
  currency?: string;
}

const HISTORY_STORAGE_KEY = "smartshopper_search_history_v2";

function Badge({ children, tone = "teal" }: { children: React.ReactNode; tone?: "teal" | "indigo" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function formatSpecValue(value: unknown): string {
  if (value == null) {
    return "n/a";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.slice(0, 4).map((entry) => formatSpecValue(entry)).join(" · ");
  }
  if (typeof value === "object") {
    return Object.values(value).slice(0, 4).map((entry) => formatSpecValue(entry)).join(" · ");
  }
  return String(value);
}

function SkeletonCard() {
  return (
    <div className="glass-card skeleton">
      <div className="skeleton-line skeleton-title"></div>
      <div className="skeleton-line skeleton-subtitle"></div>
      <div className="skeleton-line skeleton-text"></div>
      <div className="skeleton-badges">
        <div className="skeleton-badge"></div>
        <div className="skeleton-badge"></div>
        <div className="skeleton-badge"></div>
      </div>
    </div>
  );
}

function ResultCard({ 
  item, 
  lowCoverage, 
  searchQuery, 
  searchRunId,
  onAuthRequired 
}: { 
  item: ProductResult; 
  lowCoverage: boolean;
  searchQuery?: string;
  searchRunId?: string;
  onAuthRequired?: () => void;
}) {
  const specs = Object.entries(item.specs ?? {})
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${formatSpecValue(value)}`);
  const finalScorePercent = Math.round((item.final_score ?? 0) * 100);
  const credibilityPercent = Math.round((item.credibility_score ?? 0) * 100);
  const explanation = item.explanation || "No summary available yet.";

  const structuredDataAvailable = !lowCoverage && specs.length > 0 && (item.credibility_score ?? 0) >= 0.15;

  return (
    <div className="glass-card result-card">
      <div className="card-header">
        <div className="card-info">
          <h3 className="card-title">{item.title}</h3>
          {item.brand && <p className="card-brand">{item.brand}</p>}
          <p className="card-specs">
            {structuredDataAvailable ? specs.join(" • ") : "Structured specifications unavailable for this result"}
          </p>
        </div>
        <div className="card-price">
          <div className="price">
            {item.price != null ? `${item.currency ?? "USD"} ${item.price.toLocaleString()}` : "Price unavailable"}
          </div>
          {item.domain && <div className="availability">{item.domain}</div>}
        </div>
      </div>
      <div className="card-badges">
        <Badge tone="teal">Score: {finalScorePercent}%</Badge>
        <Badge tone="indigo">Credibility: {credibilityPercent}%</Badge>
        <span className="value-label">{explanation}</span>
      </div>
      <div className="card-actions">
        <FavoriteButton
          product={item}
          searchQuery={searchQuery}
          searchRunId={searchRunId}
          onAuthRequired={onAuthRequired}
        />
        {item.url ? (
          <a className="glass-button" href={item.url} target="_blank" rel="noreferrer">
            View Source
          </a>
        ) : (
          <button className="glass-button" disabled>
            Source unavailable
          </button>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [query, setQuery] = useState("");
  const [currency, setCurrency] = useState(getDefaultCurrency());
  const [showCurrencyDropdown, setShowCurrencyDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ProductResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [intent, setIntent] = useState<string | null>(null);
  const [runSummary, setRunSummary] = useState<{
    runId: string;
    resultsCount: number;
    totalTimeMs: number;
    coverageScore: number;
    totalCostUsd: number;
  } | null>(null);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [showAuthPanel, setShowAuthPanel] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [showFavoritesPage, setShowFavoritesPage] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const authPanelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(HISTORY_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as SearchHistoryItem[];
        setHistory(parsed);
        return;
      }

      const legacy = localStorage.getItem("smartshopper_search_history_v1");
      if (legacy) {
        const parsedLegacy = JSON.parse(legacy) as Array<
          SearchHistoryItem & { budget?: number }
        >;
        const migrated = parsedLegacy.map(({ budget, ...rest }) => rest);
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(migrated));
        localStorage.removeItem("smartshopper_search_history_v1");
        setHistory(migrated);
      }
    } catch (storageError) {
      console.warn("Failed to read search history", storageError);
    }
  }, []);

  const persistHistory = (updater: (prev: SearchHistoryItem[]) => SearchHistoryItem[]) => {
    setHistory((prev) => {
      const next = updater(prev);
      try {
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(next));
      } catch (storageError) {
        console.warn("Failed to persist search history", storageError);
      }
      return next;
    });
  };

  const closeAuthPanel = () => {
    setShowAuthPanel(false);
    setAuthError(null);
  };

  const openAuthPanel = () => {
    setShowAuthPanel(true);
    setAuthError(null);
  };

  useEffect(() => {
    if (!showAuthPanel) {
      return undefined;
    }
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeAuthPanel();
      }
    };
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [showAuthPanel]);

  useEffect(() => {
    if (!showAuthPanel) {
      return undefined;
    }
    const handleClickOutside = (event: MouseEvent) => {
      if (authPanelRef.current && !authPanelRef.current.contains(event.target as Node)) {
        closeAuthPanel();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showAuthPanel]);

  const { user: currentUser, loading: isCheckingAuth, signOut } = useCurrentUser();

  const handleGoogleSignIn = async () => {
    try {
      setAuthError(null);
      const { authorization_url } = await fetchGoogleAuthorizationUrl("/");
      window.location.href = authorization_url;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to start Google sign-in";
      setAuthError(message);
    }
  };

  const handleLogout = async () => {
    try {
      await signOut();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to log out";
      setAuthError(message);
    }
  };

  const executeSearch = async (searchQuery: string) => {
    const trimmedQuery = searchQuery.trim();
    if (trimmedQuery.length < 2) {
      setError("Please enter at least two characters to search.");
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);
    setWarnings([]);

    const payload = {
      query: trimmedQuery,
      max_results: 10,
    };

    try {
      const response: SearchResponse = await searchProducts(payload, controller.signal);
      const filteredResults = (response.results || []).filter((product) => {
        if (currency && product.currency && product.currency !== currency) {
          return false;
        }
        return true;
      });

      setResults(filteredResults);
      setIntent(response.intent ?? null);
      setWarnings(response.warnings || []);

      if (response.errors && response.errors.length > 0) {
        setError(response.errors.join(" | "));
      }

      const metrics = response.execution_metrics;
      setRunSummary({
        runId: response.run_id,
        resultsCount: filteredResults.length,
        totalTimeMs: metrics?.total_time_ms ?? 0,
        coverageScore: metrics?.coverage_score ?? 0,
        totalCostUsd: metrics?.total_cost_usd ?? 0,
      });

      const entry: SearchHistoryItem = {
        query: trimmedQuery,
        runId: response.run_id,
        timestamp: new Date().toISOString(),
        topTitle: response.results[0]?.title,
        totalTimeMs: metrics?.total_time_ms ?? 0,
        coverageScore: metrics?.coverage_score ?? 0,
        currency,
      };

      persistHistory((prev) => {
        const filtered = prev.filter((item) => item.query.toLowerCase() !== trimmedQuery.toLowerCase());
        return [entry, ...filtered].slice(0, 6);
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const message = err instanceof Error ? err.message : "Search failed";
      setError(message);
      setResults([]);
      setRunSummary(null);
      setIntent(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    executeSearch(query);
  };

  const handleQueryChange = (newQuery: string) => {
    setQuery(newQuery);

    const detection = detectPriceFromQuery(newQuery);
    if (detection.currency !== null) {
      setCurrency(detection.currency);
    }
  };

  const handlePopularClick = (term: string) => {
    handleQueryChange(term);
    executeSearch(term);
  };

  const handleHistoryClick = (item: SearchHistoryItem) => {
    if (item.currency) {
      setCurrency(item.currency);
    }
    handleQueryChange(item.query);
    executeSearch(item.query);
  };

  const hasLoaded = runSummary != null || results.length > 0;

  useEffect(() => {
    if (currentUser && showAuthPanel) {
      closeAuthPanel();
    }
  }, [currentUser, showAuthPanel]);

  // Close currency dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showCurrencyDropdown) {
        const target = event.target as Element;
        if (!target.closest('.unified-price-control')) {
          setShowCurrencyDropdown(false);
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showCurrencyDropdown]);

  const lowCoverageRun = runSummary ? runSummary.coverageScore < 0.1 : false;
  const coverageWarningMessage = runSummary
    ? `Low content coverage (${(runSummary.coverageScore * 100).toFixed(0)}%) - results may be incomplete`
    : "";
  const showCoverageBanner =
    lowCoverageRun && !warnings.some((warning) => warning.toLowerCase().includes("coverage"));

  return (
    <div className="app">
      {/* Background */}
      <div className="background">
        <div className="gradient-overlay"></div>
      </div>

      {/* Header */}
      <header className="header">
        <div className="header-brand">
          <div className="logo-container">
            <img
              src="/logo.png"
              alt="SmartShopper"
              className="logo-image"
            />
          </div>
          <div className="brand-text">
            <div className="brand-name">SmartShopper</div>
            <div className="brand-tagline">Search smarter. Shop better.</div>
          </div>
        </div>
        <nav className="nav">
          <div className="nav-actions">
            <div className="unified-price-control nav-currency-control">
              <button
                type="button"
                className="price-display nav-currency-button"
                onClick={() => setShowCurrencyDropdown(!showCurrencyDropdown)}
                aria-haspopup="listbox"
                aria-expanded={showCurrencyDropdown}
              >
                <span className="currency-symbol">{getCurrencySymbol(currency)}</span>
                <span className="currency-code">{currency}</span>
                <span className="dropdown-arrow">▼</span>
              </button>
              {showCurrencyDropdown && (
                <div className="currency-dropdown nav-currency-dropdown">
                  <div className="currency-list" role="listbox">
                    {CURRENCIES.map((curr) => (
                      <div
                        key={curr.code}
                        className={`currency-option ${currency === curr.code ? 'selected' : ''}`}
                        onClick={() => {
                          setCurrency(curr.code);
                          setShowCurrencyDropdown(false);
                        }}
                        role="option"
                        aria-selected={currency === curr.code}
                      >
                        <span className="currency-symbol">{curr.symbol}</span>
                        <span className="currency-name">{curr.name}</span>
                        <span className="currency-code">{curr.code}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {currentUser ? (
              <div className="nav-user">
                <button 
                  type="button" 
                  className="glass-button nav-button button-with-icon" 
                  onClick={() => setShowFavoritesPage(true)}
                  title="View favorites"
                >
                  <Heart className="icon icon-inline" aria-hidden="true" />
                  <span>Favorites</span>
                </button>
                <div className="nav-user-info">
                  <span className="nav-user-name">{currentUser.full_name || currentUser.email}</span>
                  <span className="nav-user-email">{currentUser.email}</span>
                </div>
                <button type="button" className="glass-button nav-button" onClick={handleLogout}>
                  Sign out
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="glass-button nav-button"
                onClick={openAuthPanel}
                disabled={isCheckingAuth}
              >
                {isCheckingAuth ? "Checking…" : "Sign in"}
              </button>
            )}
          </div>
        </nav>
      </header>

      {/* Main Content */}
      <main className="main">
        {/* Hero Section */}
        <section className="hero">
          <div className="glass-panel hero-panel">
            <h1 className="hero-title">
              Find the <span style={{ color: brand.teal }}>best deals</span> with an
              <span style={{ color: brand.indigo }}> AI shopping assistant</span>
            </h1>
            <p className="hero-subtitle">
              Compare products across trusted sources, see value scores, and set price-drop alerts.
            </p>

            {/* Search Form */}
            <form className="search-form" onSubmit={handleSubmit}>
              <div className="search-input-wrapper">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => handleQueryChange(e.target.value)}
                  placeholder="Try: best laptops under €1000 for programming"
                  className="search-input"
                />
              </div>

              <div className="search-controls">
                <button type="submit" className="search-button" disabled={loading}>
                  {loading ? "Searching…" : "Search"}
                </button>
              </div>
            </form>

            {error && (
              <div className="error-banner" role="alert">
                {error}
              </div>
            )}

            {warnings.length > 0 && !error && (
              <div className="warning-banner" role="status">
                {warnings.join(" • ")}
              </div>
            )}
            {showCoverageBanner && (
              <div className="warning-banner" role="status">
                {coverageWarningMessage}
              </div>
            )}

            {/* Popular Searches */}
            <div className="popular-searches">
              <span className="popular-label">Popular:</span>
              {["ultralight laptop", "mechanical keyboard", "mirrorless camera", "noise-canceling headphones"].map((term) => (
                <button
                  key={term}
                  type="button"
                  onClick={() => handlePopularClick(term)}
                  className="popular-button"
                >
                  {term}
                </button>
              ))}
            </div>

            {history.length > 0 && (
              <div className="history-panel">
                <div className="history-title">Recent searches</div>
                <div className="history-items">
                  {history.map((item) => (
                    <button
                      key={`${item.runId}-${item.timestamp}`}
                      type="button"
                      className="history-button"
                      onClick={() => handleHistoryClick(item)}
                    >
                      <div className="history-query">{item.query}</div>
                      <div className="history-meta">
                        <span>{item.topTitle ? item.topTitle : "No results"}</span>
                        <span>• Coverage {(item.coverageScore * 100).toFixed(0)}%</span>
                        {item.currency && (
                          <span>• Currency {item.currency}</span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Results Section */}
        <section className="results">
          <div className="results-header">
            <h2 className="results-title">Results</h2>
            <div className="results-count">
              {loading
                ? "Searching…"
                : runSummary
                ? `${runSummary.resultsCount} matches`
                : `${results.length} matches`}
            </div>
          </div>

          {intent && (
            <div className="intent-badge">Detected intent: {intent}</div>
          )}

          {runSummary && (
            <div className="metrics-panel">
              <div>
                <span className="metric-label">Total time</span>
                <span className="metric-value">{(runSummary.totalTimeMs / 1000).toFixed(2)}s</span>
              </div>
              <div>
                <span className="metric-label">Coverage</span>
                <span className="metric-value">{(runSummary.coverageScore * 100).toFixed(0)}%</span>
              </div>
              <div>
                <span className="metric-label">Cost</span>
                <span className="metric-value">${runSummary.totalCostUsd.toFixed(4)}</span>
              </div>
            </div>
          )}

          <div className="results-grid">
            {loading
              ? Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
              : results.map((r, index) => (
                  <ResultCard 
                    key={`${r.title}-${index}`} 
                    item={r} 
                    lowCoverage={lowCoverageRun}
                    searchQuery={query}
                    searchRunId={runSummary?.runId}
                    onAuthRequired={openAuthPanel}
                  />
                ))}
          </div>

          {!loading && hasLoaded && results.length === 0 && (
            <div className="empty-state">No results yet. Try refining your query or adjusting filters.</div>
          )}
        </section>
      </main>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <div className="footer-copyright">© {new Date().getFullYear()} SmartShopper</div>
          <div className="footer-links">
            <a href="mailto:zuko.bronja@gmail.com" className="footer-link">Contact</a>
          </div>
        </div>
      </footer>

      {showAuthPanel && (
        <div className="auth-overlay" role="dialog" aria-modal="true">
          <div className="auth-panel glass-panel" ref={authPanelRef}>
            <div className="auth-header">
              <h2>Sign in to SmartShopper</h2>
              <p>Choose a sign-in method to continue.</p>
            </div>
            {authError && (
              <div className="error-banner" role="alert">
                {authError}
              </div>
            )}
            <div className="auth-actions">
              <button type="button" className="auth-option" onClick={handleGoogleSignIn}>
                <span className="auth-option-title">Continue with Google</span>
                <span className="auth-option-subtitle">Use your Google account for instant access.</span>
              </button>
              <button
                type="button"
                className="auth-option"
                onClick={() => setAuthError("Email sign-in is coming soon. Please use Google for now.")}
              >
                <span className="auth-option-title">Continue with Email</span>
                <span className="auth-option-subtitle">Register or sign in with your email address.</span>
              </button>
            </div>
            <button type="button" className="auth-close" onClick={closeAuthPanel}>
              Close
            </button>
          </div>
        </div>
      )}

      {/* Favorites Page */}
      {showFavoritesPage && (
        <FavoritesPage onClose={() => setShowFavoritesPage(false)} />
      )}
    </div>
  );
}
