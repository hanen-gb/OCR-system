/**
 * AppContext — theme (dark/light) + langue (fr/en) globaux
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { type Lang, type TranslationKey, t as translate } from "@/lib/i18n";

type Theme = "dark" | "light";

interface AppContextValue {
  theme: Theme;
  toggleTheme: () => void;
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TranslationKey) => string;
}

const AppContext = createContext<AppContextValue | null>(null);

const THEME_KEY = "odsinet_theme";
const LANG_KEY  = "odsinet_lang";

export function AppProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(THEME_KEY) as Theme) ?? "dark"
  );
  const [lang, setLangState] = useState<Lang>(
    () => (localStorage.getItem(LANG_KEY) as Lang) ?? "en"
  );

  // Applique la classe sur <html>
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "light") {
      root.classList.add("light");
    } else {
      root.classList.remove("light");
    }
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem(LANG_KEY, l);
  };

  const t = (key: TranslationKey) => translate(lang, key);

  return (
    <AppContext.Provider value={{ theme, toggleTheme, lang, setLang, t }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
