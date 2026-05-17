import { router } from "./router";
import { Providers } from "./providers";

export function App() {
  return <Providers router={router} />;
}
