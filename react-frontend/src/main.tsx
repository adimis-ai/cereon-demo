import App from "./App";
import "./index.css"
import { createRoot } from "react-dom/client";
import { ThemeProvider } from "./contexts/theme-provider";

createRoot(document.getElementById("root")!).render(
  <ThemeProvider defaultTheme="dark">
    <App />
  </ThemeProvider>
);
