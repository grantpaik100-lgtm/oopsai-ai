import { useEffect, useState } from "react";
import DevIncidentScenarios from "./pages/DevIncidentScenarios";
import InputFlow from "./pages/InputFlow";

function usePathname() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const handler = () => setPath(window.location.pathname);
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);
  return path;
}

export default function App() {
  const path = usePathname();
  if (path === "/dev/incident-scenarios") {
    return <DevIncidentScenarios />;
  }
  return <InputFlow />;
}
