import { FinishHubSpotInstall } from "./finish-client";

export default function HubSpotFinishPage({ params }: { params: { code: string } }) {
  return <FinishHubSpotInstall code={decodeURIComponent(params.code)} />;
}
