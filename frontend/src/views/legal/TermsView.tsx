import { LegalList, LegalPage, LegalSection } from "./LegalPage";

/** Terms of use at `/terms`. Copy is owner-supplied. */
export function TermsView() {
  return (
    <LegalPage title="Terms of use" updated="18/08/2026">
      <LegalSection title="1. Introduction">
        <p>
          These Terms of Use (&quot;Terms&quot;) govern your access to and use of Policy Atlas (the
          &quot;Tool&quot;), an AI-powered evidence synthesis prototype owned and operated by Nesta
          (&quot;we,&quot; &quot;us,&quot; or &quot;our&quot;), a charity registered in England and
          Wales (No. 1144091) and Scotland (No. SC042833).
        </p>
        <p>
          By accessing or using the Tool, you agree to be bound by these Terms. If you do not agree,
          strictly do not use the Tool.
        </p>
      </LegalSection>

      <LegalSection title="2. Nature of the Tool. Please read this carefully.">
        <p>
          <strong>Beta Status:</strong> Policy Atlas is currently in a Beta testing phase. It is a
          prototype, not a finished product. We may modify, suspend, or discontinue features at any
          time without notice.
        </p>
        <p>
          <strong>AI Limitations:</strong> This Tool utilises Large Language Models (LLMs) to
          synthesise information. AI can make errors, misinterpret text, or generate
          &quot;hallucinations&quot; (plausible-sounding but incorrect information).
        </p>
        <p>
          <strong>No Reliance:</strong> The content provided by Policy Atlas is for informational and
          research purposes only. It does not constitute policy advice. You must verify all
          summaries, citations, and &quot;blueprints&quot; against the original source documents
          before using them in official policy decisions.
        </p>
        <p>
          We don&apos;t guarantee that the site will always be available or free from errors or
          viruses. You are responsible for installing virus-checking software to protect your
          hardware. As far as legally possible, we exclude all liability for any loss or damage
          suffered as a result of using or accessing our site, whether direct or indirect, and
          however arising, including any loss of data or damage caused by downloading content from
          our site.
        </p>
      </LegalSection>

      <LegalSection title="3. Authorised use">
        <p>
          Access to this Tool is currently restricted to authorised participants in the user testing
          phase. You agree to:
        </p>
        <LegalList>
          <li>Keep your login credentials (managed via Amazon Cognito) confidential.</li>
          <li>
            Use the Tool only for lawful professional purposes related to evidence synthesis and
            policy design.
          </li>
          <li>
            Not use the Tool to input personal data, confidential and/or classified government
            information (Official-Sensitive or above).
          </li>
        </LegalList>
      </LegalSection>

      <LegalSection title="4. Intellectual property">
        <p>
          <strong>Nesta&apos;s Rights:</strong> We own the intellectual property rights to the Policy
          Atlas interface, code, and methodology. Such information, materials and logos are protected
          by copyright laws and treaties around the world. All such rights are reserved. We make no
          representation or warranty about the content, including in relation to non-infringement of
          intellectual property rights.
        </p>
        <p>
          <strong>Third-Party Content:</strong> The Tool aggregates data indexed by OpenAlex and
          Overton. Intellectual property rights in the underlying documents remain with their
          respective authors/publishers.
        </p>
        <p>
          <strong>Your Inputs:</strong> You retain rights to the queries you input. You grant us a
          license to use these inputs to operate the Tool and improve our search algorithms.
        </p>
      </LegalSection>

      <LegalSection title="5. Third-party services">
        <p>
          The Tool relies on third-party services. By using the Tool, you acknowledge our use of:
        </p>
        <LegalList>
          <li>Amazon Bedrock: For text generation and summarisation.</li>
          <li>OpenAI: For text generation and summarisation.</li>
          <li>Amazon Cognito: For user authentication.</li>
          <li>Amazon Aurora PostgreSQL: For database management.</li>
          <li>OpenAlex and Overton: For data sourcing.</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="6. Liability">
        <p>To the maximum extent permitted by law:</p>
        <LegalList>
          <li>
            The Tool is provided &quot;as is&quot; and &quot;as available&quot; without warranties of
            any kind, specifically regarding the accuracy or completeness of AI-generated summaries.
          </li>
          <li>
            Nesta shall not be liable for any direct, indirect, or consequential loss arising from
            your use of the Tool, including any reliance placed on the AI-generated content.
          </li>
          <li>
            We do not exclude liability for death or personal injury caused by our negligence or for
            fraud.
          </li>
        </LegalList>
      </LegalSection>

      <LegalSection title="7. Variation">
        <p>
          These Terms may be varied from time to time. If you use the site after any change has been
          made, you will be deemed to have accepted the change.
        </p>
      </LegalSection>

      <LegalSection title="8. Feedback">
        <p>
          As a pilot user, you agree that any feedback, suggestions, or ideas you provide regarding
          the Tool may be used by Nesta without any obligation to compensate you.
        </p>
      </LegalSection>

      <LegalSection title="9. Governing law">
        <p>
          These Terms are governed by English law. The courts of England and Wales have exclusive
          jurisdiction.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
