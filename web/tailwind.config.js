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
        background: "#08090a", // Near-black editorial canvas
        surface: {
          DEFAULT: "#0f1012", // Subtle charcoal for necessary surfaces
          raised: "#141518",
          subtle: "#0b0c0d",
        },
        border: {
          DEFAULT: "#1e2023", // Exceptionally subtle neutral border
          subtle: "#161719",
          muted: "#272a2e",
        },
        foreground: {
          DEFAULT: "#f2f2f0", // Warm white primary text
          muted: "#9d9ea1", // Secondary neutral gray
          dim: "#6b6c70", // Tertiary / metadata
        },
        // Semantic security states strictly for actual verdicts
        security: {
          block: "#ef4444",
          blockBg: "rgba(239, 68, 68, 0.08)",
          review: "#f59e0b",
          reviewBg: "rgba(245, 158, 11, 0.08)",
          allow: "#10b981",
          allowBg: "rgba(16, 185, 129, 0.08)",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          '"SFMono-Regular"',
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
