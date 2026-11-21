/**
 * auth.ts — Multi-user authentication with profiles (localStorage)
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
  photo?: string;       // base64 data URL of the profile photo
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

/**
 * Demo admin password: read from VITE_DEMO_ADMIN_PASSWORD, otherwise a random one is
 * generated on first start and printed once in the browser console.
 */
function randomPassword(length = 16): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

const DEMO_ADMIN_PASSWORD: string = (() => {
  const fromEnv = import.meta.env.VITE_DEMO_ADMIN_PASSWORD as string | undefined;
  if (fromEnv) return fromEnv;
  const generated = randomPassword();
  console.warn(`[demo] No VITE_DEMO_ADMIN_PASSWORD set — generated admin password: ${generated}`);
  return generated;
})();

/** Default users (always present) */
const DEFAULT_USERS: UserProfile[] = [
  {
    username: "admin",
    password: DEMO_ADMIN_PASSWORD,
    displayName: "Administrator",
    email: "admin@example.com",
    role: "admin",
    avatarColor: AVATAR_COLORS[0],
    bio: "Demo administrator account (local demo only — change it before any deployment).",
    createdAt: "2026-01-01",
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
    // Merge the defaults (in case they were deleted)
    const merged = [...DEFAULT_USERS];
    for (const u of stored) {
      if (!merged.find((d) => d.username === u.username)) {
        merged.push(u);
      } else {
        // Update the default with the data modified by the user
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
  // Update the session if this is the current user
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
  // Do not delete the default admins
  if (username === "admin") return false;
  const users = loadUsers().filter((u) => u.username !== username);
  saveUsers(users);
  return true;
}

export function getHistoryKey(username: string): string {
  return `odsinet_history_${username}`;
}

export { AVATAR_COLORS };
