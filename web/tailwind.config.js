/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#090d16", // Deep obsidian/slate
        foreground: "#f1f5f9",
        card: {
          DEFAULT: "#0f172a",
          foreground: "#f8fafc",
          border: "#1e293b",
        },
        popover: {
          DEFAULT: "#0f172a",
          foreground: "#f8fafc",
        },
        primary: {
          DEFAULT: "#6366f1", // Indigo
          foreground: "#ffffff",
          hover: "#4f46e5",
        },
        secondary: {
          DEFAULT: "#1e293b",
          foreground: "#94a3b8",
        },
        muted: {
          DEFAULT: "#1e293b",
          foreground: "#94a3b8",
        },
        accent: {
          DEFAULT: "#06b6d4", // Cyan
          foreground: "#083344",
        },
        destructive: {
          DEFAULT: "#ef4444", // Red
          foreground: "#ffffff",
        },
        warning: {
          DEFAULT: "#f59e0b", // Amber
          foreground: "#ffffff",
        },
        success: {
          DEFAULT: "#10b981", // Emerald
          foreground: "#ffffff",
        },
        border: "#1e293b",
        input: "#1e293b",
        ring: "#6366f1",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
