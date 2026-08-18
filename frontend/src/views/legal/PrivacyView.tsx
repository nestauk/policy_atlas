import { ExternalNoticeLink, LegalList, LegalPage, LegalSection } from "./LegalPage";

const AWS_PRIVACY = "https://aws.amazon.com/privacy/";
const OPENAI_PRIVACY = "https://openai.com/policies/privacy-policy";

/** Privacy notice at `/privacy`. Copy is owner-supplied. */
export function PrivacyView() {
  return (
    <LegalPage title="Privacy notice">
      <LegalSection title="1. Introduction">
        <p>
          This website belongs to Nesta - you can find our full details below. This privacy notice
          explains how Nesta uses personal information we collect via this site. We are committed to
          protecting your privacy and we take all reasonable precautions to safeguard personal
          information. This website contains links to other websites. We encourage you to read the
          privacy statements on the other websites you visit.
        </p>
      </LegalSection>

      <LegalSection title="2. Contact details">
        <p>
          Nesta is the data controller and is responsible for your personal data collected in
          connection with this project. This means that we will be responsible for keeping your
          information safe and only using it for the purposes set out in this notice.
        </p>
        <p>
          We have appointed a Data Protection Officer (DPO) who is responsible for overseeing
          questions in relation to this privacy notice. If you have any questions about this privacy
          notice, including any requests to exercise your legal rights in relation to your personal
          data, please contact the DPO and provide enough information to identify yourself (e.g. your
          name and address):
        </p>
        <p>
          Email: <a href="mailto:dpo@nesta.org.uk">dpo@nesta.org.uk</a>
        </p>
        <p>Post: 58 Victoria Embankment London UK EC4Y 0DS</p>
        <p>
          If you are unhappy about how we use your personal data or have a complaint, you have the
          right to make a complaint at any time to the Information Commissioner&apos;s Office (ICO),
          the UK supervisory authority for data protection issues. We would, however, appreciate the
          chance to deal with your concerns before you approach the ICO so please do contact us in
          the first instance.
        </p>
      </LegalSection>

      <LegalSection title="3. What personal data will we collect?">
        <p>
          Policy Atlas is committed to maintaining user privacy and strictly minimising data
          retention. We collect only the following data points:
        </p>
        <p>
          <strong>Email Address:</strong> This is the only user-specific identifier we store. It
          serves the essential purpose of linking your search activity to your account, allowing you
          to reliably retrieve your saved search results.
        </p>
        <p>
          <strong>Search Queries &amp; Results:</strong> We store the text of the queries you input
          and the results generated to populate your evidence blueprints.
        </p>
      </LegalSection>

      <LegalSection title="4. What we do not collect">
        <p>
          To protect your privacy, we have explicitly excluded the collection of metadata often
          tracked by web applications. For the avoidance of doubt, we do not collect, process, or
          store IP addresses and device information.
        </p>
      </LegalSection>

      <LegalSection title="5. What do we do with information we collect and what is our legal basis for this?">
        <p>
          The purpose for which we are processing your personal data is to provide you with access to
          the Policy Atlas website and platform.
        </p>
        <p>
          <strong>Legal basis.</strong> Data protection law requires us to have a specific legal
          basis for processing your personal data. For this project, our lawful basis will be:
        </p>
        <p>
          <strong>Legitimate business interest:</strong> We have a legitimate business interest in
          delivering the Policy Atlas platform. The project fulfils our organisation&apos;s aims
          including undertaking innovative research and information activities that will deliver
          social impact.
        </p>
      </LegalSection>

      <LegalSection title="6. Who has access to your information?">
        <p>
          Your information will be accessed by a limited number of advisors in our team working on
          this project.
        </p>
        <p>
          In addition, we may disclose your information to third parties in connection with the
          purposes of processing your personal data set out in this notice. These third parties may
          include:
        </p>
        <LegalList>
          <li>Other companies in our group;</li>
          <li>
            Regulators, law enforcement bodies and the courts, in order to comply with applicable
            laws and regulations, assist with regulatory enquiries, and cooperate with court mandated
            processes, including the conduct of litigation;
          </li>
        </LegalList>
        <p>
          We may also disclose your personal information if required by law, or to protect or defend
          ourselves or others against illegal or harmful activities, or as part of a reorganisation
          or restructuring of our organisations.
        </p>
        <p>
          For authentication &amp; credentials, we use Amazon Cognito to securely manage user
          identities and logins. Policy Atlas does not directly view or store your password. For further information, see <ExternalNoticeLink href={AWS_PRIVACY}>Amazon Web Services privacy policy</ExternalNoticeLink>.
        </p>
        <p>
          For data storage &amp; security, your user email, search queries, and search results are
          stored in Amazon Aurora PostgreSQL, hosted in Nesta&apos;s AWS environment.
        </p>
        <p>In relation to AI &amp; Third-Party Processors, we use the following services to operate the tool:</p>
        <LegalList>
          <li>
            <strong>Amazon Bedrock:</strong> Processes anonymised search queries to generate summaries,
            using OpenAI models via the AWS Bedrock API. Bedrock inputs and outputs are not shared
            with model providers and are not used to train base models.
          </li>
          <li>
            <strong>OpenAI:</strong> Processes anonymised search queries to generate summaries. OpenAI
            does not use data submitted via their API to train their models. See{" "}
            <ExternalNoticeLink href={OPENAI_PRIVACY}>OpenAI&apos;s privacy notice</ExternalNoticeLink>
            .
          </li>
          <li>
            <strong>Overton &amp; OpenAlex:</strong> These are our data sources; search keywords are
            sent to these APIs to retrieve relevant documents, but no personal data is shared with
            them.
          </li>
        </LegalList>
      </LegalSection>

      <LegalSection title="7. Data retention">
        <p>
          We retain your email and search history only for as long as user testing is active to allow
          you to use the tool. Upon the conclusion of the pilot (or upon your request), your personal
          data will be permanently deleted from our Amazon Aurora PostgreSQL database.
        </p>
      </LegalSection>

      <LegalSection title="8. Your legal rights">
        <p>
          Under certain circumstances, you have rights under data protection laws in relation to your
          personal data, including rights to:
        </p>
        <LegalList>
          <li>
            <strong>Request access to your personal data:</strong> this enables you to receive a copy
            of the personal data we hold about you and to check we are lawfully processing it.
          </li>
          <li>
            <strong>Request correction of your personal data:</strong> this enables you to have any
            incomplete or inaccurate data we hold about you corrected.
          </li>
          <li>
            <strong>Request erasure of your personal data:</strong> this enables you to ask us to
            delete or remove personal data where there is no good reason for us continuing to process
            it.
          </li>
          <li>
            <strong>Object to processing of your personal data:</strong> for example, you can object
            where we are relying on a legitimate interest (or those of a third party) and there is
            something about your particular situation which makes you want to object to processing on
            this ground as you feel it impacts on your fundamental rights and freedoms.
          </li>
          <li>
            <strong>Request restriction of processing your personal data:</strong> This enables you to
            ask us to suspend the processing of your personal data.
          </li>
          <li>
            <strong>Data portability:</strong> Where the processing takes place on the basis of your
            consent or contract, and is carried out by automated means, you have the right to request
            that we provide your personal data to you in a machine-readable format, or transmit it to
            a third party data controller, where technically feasible.
          </li>
          <li>
            <strong>Right to withdraw consent to the processing of your personal data:</strong> This
            applies where we have relied on consent to process personal data. Please note that
            withdrawal of consent will not affect the lawfulness of any processing carried out before
            withdrawing your consent.
          </li>
        </LegalList>
        <p>
          If you wish to exercise any of the rights set out above, please send your specific request
          to the Data Protection Officer using the contact details provided at section 2.
        </p>
        <p>
          It is important to understand that the extent to which these rights apply to research will
          vary and that in some circumstances your rights may be restricted. Please also note that we
          can only comply with a request to exercise your rights during the period for which we hold
          personal information that identifies you. If personal data has been irreversibly anonymised
          and has become part of the research data set, it will not be possible for us to comply.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
