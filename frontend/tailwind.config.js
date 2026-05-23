/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Soft pastel surface palette (used across the app chrome)
        cream:  "#FBF7F0",
        sand:   "#F2EBDC",
        mist:   "#EEF4F8",
        peach:  "#FCE7D8",
        rosey:  "#F8D7DA",
        sage:   "#DDEDE0",
        sky2:   "#DCE9F4",
        ink:    "#3F3A4C", // text
        ink2:   "#6B6477", // muted text
        // Status accents kept readable on a light surface
        live:   "#3FA372",
        scheduled: "#9A93A7",
        warn:   "#D89B3F",
        crit:   "#D26464",
      },
    },
  },
  plugins: [],
};
