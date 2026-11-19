import { Config } from "@remotion/cli/config";

// Use the installed Chrome (Remotion's own browser download is blocked here),
// and keep concurrency modest so Chrome doesn't throttle background render tabs.
Config.setBrowserExecutable("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
Config.setConcurrency(4);
Config.setDelayRenderTimeoutInMilliseconds(120000);
Config.setCodec("h264");
Config.setCrf(18);
