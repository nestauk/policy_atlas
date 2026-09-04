import { useState } from "react";
import { Link } from "react-router";

import { useAuth } from "../../auth";
import { acceptDevToken } from "../../auth/DevTokenAuthProvider";
import { DevTokenLoginPanel } from "../../auth/DevTokenLoginPanel";
import { AUTH_RETURN_TO_KEY } from "../../auth/OidcAuthProvider";
import { FoldMarkAnimated } from "../../ui/brand/FoldMarkAnimated";
import { SplashFeatureSteps } from "./SplashFeatureSteps";
import { SplashField } from "./SplashField";
import { SPLASH_PROSE } from "./splashTypography";
import { WaitlistForm } from "./WaitlistForm";

/** Set true once product screenshots replace the dashed placeholders. */
const SHOW_SPLASH_FEATURE_STEPS = false;

/**
 * Logged-out marketing home — fold-mark constellation, Request-access
 * waitlist form, and Sign-in into Cognito (or the dev-token panel when
 * OIDC is unset). Feature steps 01–06 stay behind
 * {@link SHOW_SPLASH_FEATURE_STEPS} until screenshots are ready.
 */
export function SplashView() {
  const auth = useAuth();
  const [showDevSignIn, setShowDevSignIn] = useState(false);
  const oidcConfigured = Boolean(import.meta.env.VITE_OIDC_AUTHORITY);

  const onSignIn = () => {
    if (!oidcConfigured) {
      setShowDevSignIn(true);
      document.getElementById("access")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo === "/" ? "/" : returnTo);
    void auth.signIn();
  };

  return (
    <div className="min-h-screen bg-navy text-white">
      <header className="flex justify-center border-b border-white/15 px-6">
        <div className="flex h-16 w-full max-w-[1180px] items-center gap-6">
          <div className="flex min-w-0 items-center gap-1.25">
            <FoldMarkAnimated />
            <span className="whitespace-nowrap font-display text-heading font-extrabold tracking-[-0.02em]">
              Policy <b className="font-extrabold text-aqua">Atlas</b>
            </span>
          </div>
        </div>
      </header>

      <section className="relative flex min-h-[calc(100vh-64px)] items-center justify-center overflow-hidden px-6 py-20">
        <SplashField />
        <div className="relative z-10 w-full max-w-[1180px]">
          <div id="splash-copy" className="max-w-[20em]">
            <h1 className="m-0 font-display text-[clamp(40px,5.4vw,68px)] font-extrabold leading-[1.02] tracking-[-0.025em] text-pretty text-white">
              Create policy plans you can trust
            </h1>
            <p className={`mt-6 max-w-[26em] ${SPLASH_PROSE} text-navy-muted text-pretty`}>
              AI-powered tool to put evidence at the heart of policymaking
            </p>
            <div className="mt-9 flex flex-wrap gap-3.5">
              <a
                href="#access"
                className="cutout inline-flex min-h-12 items-center bg-white px-[22px] text-lead font-extrabold text-navy no-underline hover:bg-aqua"
              >
                Request access
              </a>
              <button
                type="button"
                onClick={onSignIn}
                className="inline-flex min-h-12 cursor-pointer items-center border border-white/40 bg-transparent px-[22px] text-lead font-extrabold text-white hover:border-aqua hover:text-aqua"
              >
                Sign in
              </button>
            </div>
          </div>
        </div>
      </section>

      {SHOW_SPLASH_FEATURE_STEPS ? <SplashFeatureSteps /> : null}

      <section
        id="access"
        className="flex justify-center border-t border-white/15 bg-paper px-6 pb-24 text-navy"
      >
        <div className="w-full max-w-[1180px] pt-[72px]">
          <div className="w-full max-w-xl">
            <h2 className="m-0 font-display text-title font-extrabold tracking-[-0.02em] text-navy">
              Request access
            </h2>
            <p className={`mt-3 ${SPLASH_PROSE} text-grey`}>
              Tell us a little about yourself. We review requests and get in touch when a place opens
              up.
            </p>
            <div className="mt-8">
              <WaitlistForm />
            </div>
          </div>
          {showDevSignIn && !oidcConfigured && (
            <div className="mt-10 max-w-xl border-t border-line pt-8">
              <p className="mb-4 text-meta text-grey">
                Local development — paste a dev-issuer token to enter the app.
              </p>
              <DevTokenLoginPanel embedded onSubmit={acceptDevToken} />
            </div>
          )}
        </div>
      </section>

      <section
        id="links"
        className="flex justify-center border-t border-white/15 bg-navy px-6 pb-24"
      >
        <div className="w-full max-w-[1180px] pt-[72px]">
          <p className={`max-w-xl ${SPLASH_PROSE} text-navy-muted text-pretty`}>
            Policy Atlas is an experimental AI-powered tool developed by Nesta, the UK&apos;s
            research and innovation foundation. It is currently in private beta testing.
          </p>
          <ul className={`mt-8 flex flex-col gap-3 ${SPLASH_PROSE}`}>
            <li>
              <a
                href="https://www.nesta.org.uk/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-aqua no-underline hover:underline"
              >
                About Nesta
              </a>
            </li>
            <li>
              <a
                href="https://www.nesta.org.uk/project/policy-atlas-harnessing-ai-to-improve-policy-design/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-aqua no-underline hover:underline"
              >
                Policy Atlas project page
              </a>
            </li>
            <li>
              <a
                href="https://substack.com/@policyatlas1"
                target="_blank"
                rel="noopener noreferrer"
                className="text-aqua no-underline hover:underline"
              >
                Policy Atlas Substack
              </a>
            </li>
          </ul>
          <p className={`mt-10 ${SPLASH_PROSE} text-white/50`}>
            <Link to="/privacy" className="text-aqua no-underline hover:underline">
              Privacy
            </Link>
            {" · "}
            <Link to="/terms" className="text-aqua no-underline hover:underline">
              Terms
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
