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
        background: "#080a0f", // Near-black dark canvas
        surface: {
          DEFAULT: "#0f141f", // Charcoal structural panels
          elevated: "#141b29", // Slightly raised layer
          subtle: "#0b0e17", // Subtle recessed background
        },
        card: {
          DEFAULT: "#0f141f",
          foreground: "#f3f4f6",
          border: "#1c2536",
        },
        border: {
          DEFAULT: "#1c2536", // Neutral hairline border
          subtle: "#161d2b",
          strong: "#28354d",
        },
        foreground: {
          DEFAULT: "#f3f4f6", // Off-white primary text
          muted: "#94a3b8", // Secondary slate text
          dim: "#64748b", // Tertiary text / metadata
        },
        // Restrained signature brand accent: Acid Lime
        brand: {
          DEFAULT: "#a3e635", // lime-400
          hover: "#bef264",
          dim: "rgba(163, 230, 53, 0.12)",
          border: "rgba(163, 230, 53, 0.3)",
        },
        // Strict semantic security states
        security: {
          block: "#ef4444", // Red - Policy block / denied
          blockBg: "rgba(239, 68, 68, 0.1)",
          blockBorder: "rgba(239, 68, 68, 0.28)",

          review: "#f59e0b", // Amber - Review / Pending
          reviewBg: "rgba(245, 158, 11, 0.1)",
          reviewBorder: "rgba(245, 158, 11, 0.28)",

          allow: "#10b981", // Emerald - Safe / Executed / Allowed
          allowBg: "rgba(16, 185, 129, 0.1)",
          allowBorder: "rgba(16, 185, 129, 0.28)",

          neutral: "#64748b", // Muted slate - Expired / Consumed
          neutralBg: "rgba(100, 116, 139, 0.1)",
          neutralBorder: "rgba(100, 116, 139, 0.28)",
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
          '"Liberation Mono"',
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
