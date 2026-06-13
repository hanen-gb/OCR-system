/**
 * auth.ts — Authentification multi-utilisateur avec profils (localStorage)
 */

export type Role = "admin" | "user";
export type Lang = "fr" | "en";
export type Theme = "dark" | "light";

export interface UserProfile {
  username: string;
  password: string;
  displayName: string;
  email: string;
  role: Role;
  avatarColor: string;
  photo?: string;       // base64 data-URL de la photo de profil
  bio: string;
  createdAt: string;
  lang: Lang;
  theme: Theme;
}

const USERS_KEY   = "odsinet_users";
const SESSION_KEY = "odsinet_session";

const AVATAR_COLORS = [
  "hsl(215 80% 55%)",
  "hsl(262 60% 55%)",
  "hsl(152 60% 40%)",
  "hsl(38 90% 50%)",
  "hsl(0 65% 55%)",
  "hsl(180 55% 40%)",
];

/** Utilisateurs par défaut (toujours présents) */
const DEFAULT_USERS: UserProfile[] = [
  {
    username: "admin",
    password: "REDACTED",
    displayName: "Administrateur",
    email: "admin@example.com",
    role: "admin",
    avatarColor: AVATAR_COLORS[0],
    bio: "Default administrator account.",
    createdAt: "2025-01-01",
    lang: "en",
    theme: "dark",
  },
  {
    username: "user",
    password: "REDACTED",
    displayName: "Goubaa Hanen",
    email: "user@example.com",
    role: "admin",
    avatarColor: AVATAR_COLORS[1],
    bio: "PFE 2025 student — ENIG Gabès.",
    createdAt: "2025-01-01",
    lang: "en",
    theme: "dark",
  },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function loadUsers(): UserProfile[] {
  const raw = localStorage.getItem(USERS_KEY);
  if (!raw) return [...DEFAULT_USERS];
  try {
    const stored: UserProfile[] = JSON.parse(raw);
    // Fusionner les defaults (au cas où ils ont été supprimés)
    const merged = [...DEFAULT_USERS];
    for (const u of stored) {
      if (!merged.find((d) => d.username === u.username)) {
        merged.push(u);
      } else {
        // Mettre à jour le default avec les données modifiées de l'utilisateur
        const idx = merged.findIndex((d) => d.username === u.username);
        merged[idx] = u;
      }
    }
    return merged;
  } catch {
    return [...DEFAULT_USERS];
  }
}

function saveUsers(users: UserProfile[]): void {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

// ── API publique ──────────────────────────────────────────────────────────────

export function getAllUsers(): UserProfile[] {
  return loadUsers();
}

export function login(username: string, password: string): UserProfile | null {
  const users = loadUsers();
  const user = users.find(
    (u) => u.username.toLowerCase() === username.toLowerCase() && u.password === password,
  );
  if (!user) return null;
  localStorage.setItem(SESSION_KEY, JSON.stringify(user));
  return user;
}

export function logout(): void {
  localStorage.removeItem(SESSION_KEY);
}

export function getSession(): UserProfile | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserProfile;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return getSession() !== null;
}

export function register(
  username: string,
  password: string,
  displayName: string,
  email: string,
): { ok: boolean; error?: string } {
  const users = loadUsers();
  if (users.find((u) => u.username.toLowerCase() === username.toLowerCase())) {
    return { ok: false, error: "This email is already registered." };
  }
  const newUser: UserProfile = {
    username: username.trim(),
    password,
    displayName: displayName.trim() || username,
    email: email.trim(),
    role: "user",
    avatarColor: AVATAR_COLORS[users.length % AVATAR_COLORS.length],
    bio: "",
    createdAt: new Date().toISOString().slice(0, 10),
    lang: "en",
    theme: "dark",
  };
  users.push(newUser);
  saveUsers(users);
  return { ok: true };
}

export function updateProfile(
  username: string,
  updates: Partial<Pick<UserProfile, "displayName" | "email" | "bio" | "avatarColor" | "photo" | "lang" | "theme">>,
): boolean {
  const users = loadUsers();
  const idx = users.findIndex((u) => u.username === username);
  if (idx === -1) return false;
  users[idx] = { ...users[idx], ...updates };
  saveUsers(users);
  // Mettre à jour la session si c'est l'utilisateur courant
  const session = getSession();
  if (session?.username === username) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(users[idx]));
  }
  return true;
}

export function changePassword(
  username: string,
  currentPassword: string,
  newPassword: string,
): { ok: boolean; error?: string } {
  const users = loadUsers();
  const idx = users.findIndex((u) => u.username === username);
  if (idx === -1) return { ok: false, error: "Utilisateur introuvable." };
  if (users[idx].password !== currentPassword) {
    return { ok: false, error: "wrong_password" };
  }
  users[idx] = { ...users[idx], password: newPassword };
  saveUsers(users);
  return { ok: true };
}

export function deleteUser(username: string): boolean {
  // Ne pas supprimer les admins par défaut
  if (username === "admin" || username === "user") return false;
  const users = loadUsers().filter((u) => u.username !== username);
  saveUsers(users);
  return true;
}

export function getHistoryKey(username: string): string {
  return `odsinet_history_${username}`;
}

export { AVATAR_COLORS };
