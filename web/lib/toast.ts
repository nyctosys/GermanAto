import { create } from "zustand";

export type Toast = { id: number; tone: "success" | "error"; message: string };

type Store = { toasts: Toast[]; show: (tone: Toast["tone"], message: string) => void; dismiss: (id: number) => void };

let next = 1;
const timers = new Map<number, ReturnType<typeof setTimeout>>();

/** The one list of notices on screen. Success notices clear themselves after 5 s, errors after 9 s; each can be closed at once. */
export const useToasts = create<Store>((set, get) => ({
  toasts: [],
  show: (tone, message) => {
    // The same notice twice in a row (a double action, an autosave) is shown once.
    if (get().toasts.some((t) => t.message === message && t.tone === tone)) return;
    const id = next++;
    set((s) => ({ toasts: [...s.toasts.slice(-2), { id, tone, message }] }));
    timers.set(id, setTimeout(() => get().dismiss(id), tone === "error" ? 9000 : 5000));
  },
  dismiss: (id) => {
    clearTimeout(timers.get(id));
    timers.delete(id);
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  },
}));

export const toast = {
  success: (message: string) => useToasts.getState().show("success", message),
  error: (message: string) => useToasts.getState().show("error", message),
};
