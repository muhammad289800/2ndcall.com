"""Legal page content for 2ndCall.

All content returned from this module is treated as trusted HTML and rendered via
`{{ body | safe }}` in templates/legal.html. Do NOT interpolate user input into
these strings without escaping.
"""
from __future__ import annotations

EFFECTIVE_DATE = "April 15, 2026"
CONTACT_EMAIL = "support@your2ndline.com"
LEGAL_EMAIL = "legal@your2ndline.com"
ABUSE_EMAIL = "abuse@your2ndline.com"
OPERATOR = "Dream Easy LLC"


PRIVACY_HTML = """
<h2>1. Who we are</h2>
<p>2ndCall is an Application-to-Person (A2P) SMS and programmable voice platform operated by Dream Easy LLC (\u201cwe\u201d, \u201cus\u201d, \u201c2ndCall\u201d). This Privacy Policy explains what information we collect, how we use it, and the choices you have.</p>

<h2>2. Information we collect</h2>
<h3>Account information</h3>
<ul>
  <li>Name, email address, and hashed password.</li>
  <li>Legal business name, business website, EIN / tax identifier, country of incorporation, and declared messaging use case.</li>
  <li>Acceptance timestamps for our Terms of Service and SMS Policy, along with the IP address and user-agent of the device used at registration.</li>
</ul>
<h3>Message and call metadata</h3>
<ul>
  <li>Sender and recipient phone numbers, timestamps, direction, delivery status, provider message IDs, and campaign identifiers.</li>
  <li>Message body and call recordings <em>only</em> when required to deliver the service or when explicitly enabled by you.</li>
  <li>STOP / START / HELP keyword events and the resulting opt-out / opt-in state per recipient.</li>
</ul>
<h3>Payment information</h3>
<ul>
  <li>We use Stripe as our payment processor. We do not store card numbers on our servers \u2014 only the Stripe customer ID and the last 4 digits of the payment method.</li>
</ul>
<h3>Technical information</h3>
<ul>
  <li>Log data: IP address, user-agent, request path, timestamp, HTTP status.</li>
  <li>Cookies strictly required to keep you signed in.</li>
</ul>

<h2>3. How we use information</h2>
<ul>
  <li>To deliver the messaging and voice services you request.</li>
  <li>To register your business with The Campaign Registry (TCR) and with downstream carriers (T-Mobile, AT&amp;T, Verizon) as required for 10DLC A2P messaging.</li>
  <li>To enforce opt-out requests and carrier policies.</li>
  <li>To detect abuse, fraud, and violations of our Acceptable Use Policy.</li>
  <li>To send you service, billing, and security notifications.</li>
</ul>

<h2>4. Sharing</h2>
<p>We share information with:</p>
<ul>
  <li><strong>Telecom providers</strong> (Telnyx, Twilio, SignalWire) to deliver messages and calls.</li>
  <li><strong>The Campaign Registry</strong> and its downstream carriers, for required A2P 10DLC brand and campaign registration.</li>
  <li><strong>Stripe</strong>, to process payments.</li>
  <li><strong>Law enforcement</strong>, only when compelled by valid legal process.</li>
</ul>
<p>We do not sell personal information. We do not share message content for advertising.</p>

<h2>5. Data retention</h2>
<ul>
  <li>Account and business-profile records: retained for the life of your account and for 7 years after closure to meet telecom and tax record-keeping requirements.</li>
  <li>Message and call metadata: retained for 18 months.</li>
  <li>Message body content: retained for 90 days, unless a longer period is required by law.</li>
  <li>Opt-out records: retained indefinitely so we can continue to honor STOP requests.</li>
</ul>

<h2>6. Your rights</h2>
<p>You may request access, correction, or deletion of your personal information by emailing <a href="mailto:{legal_email}">{legal_email}</a>. California residents have additional rights under the CCPA / CPRA; EEA and UK residents have rights under the GDPR. We do not knowingly collect personal information from children under 13.</p>

<h2>7. Security</h2>
<p>We encrypt data in transit with TLS 1.2+, hash passwords with scrypt, and restrict production database access to named operators. No system is perfectly secure \u2014 please report suspected vulnerabilities to <a href="mailto:{abuse_email}">{abuse_email}</a>.</p>

<h2>8. Contact</h2>
<p>Dream Easy LLC \u2014 Privacy inquiries: <a href="mailto:{legal_email}">{legal_email}</a>. Abuse reports: <a href="mailto:{abuse_email}">{abuse_email}</a>.</p>
""".format(legal_email=LEGAL_EMAIL, abuse_email=ABUSE_EMAIL)


TERMS_HTML = """
<h2>1. Acceptance</h2>
<p>These Terms of Service (\u201cTerms\u201d) govern your use of 2ndCall. By creating an account or using the service, you agree to these Terms. If you do not agree, do not use 2ndCall.</p>

<h2>2. Eligibility</h2>
<p>You may only use 2ndCall on behalf of a legitimate business or individual capacity, and only if you are at least 18 years old. Each end-customer that sends SMS through 2ndCall must be individually registered with a carrier-approved A2P 10DLC Brand and Campaign.</p>

<h2>3. Your account</h2>
<ul>
  <li>You are responsible for the accuracy of the business information you provide, including legal name, EIN / tax ID, and declared use case.</li>
  <li>You are responsible for keeping your credentials secure.</li>
  <li>We may suspend or terminate your account for violations of these Terms, the SMS Policy, or the Acceptable Use Policy \u2014 including carrier-reported violations.</li>
</ul>

<h2>4. Fees and billing</h2>
<p>Service fees are shown at checkout. You authorize us to charge your selected payment method for recurring subscriptions and usage-based charges. Messaging and voice charges are non-refundable once delivered to a carrier.</p>

<h2>5. Compliance obligations</h2>
<p>You agree that:</p>
<ul>
  <li>You will only send messages to recipients from whom you have obtained prior express written consent under the TCPA and applicable state law.</li>
  <li>You will honor opt-out requests (STOP, UNSUBSCRIBE, CANCEL, END, QUIT) within 24 hours. 2ndCall blocks further messages automatically.</li>
  <li>You will include the name of your business and opt-out instructions in your first message in any conversation.</li>
  <li>You will not use 2ndCall for SHAFT content (sex, hate, alcohol, firearms, tobacco), cannabis, illegal substances, lead-generation brokering, debt collection, loan sharking, or any content prohibited by our Acceptable Use Policy or by carriers.</li>
</ul>

<h2>6. Warranty disclaimer</h2>
<p>2ndCall is provided \u201cas is\u201d without warranties of any kind, express or implied. We do not guarantee uninterrupted service, delivery of any specific message, or any particular throughput.</p>

<h2>7. Limitation of liability</h2>
<p>To the fullest extent permitted by law, Dream Easy LLC will not be liable for any indirect, incidental, consequential, or punitive damages. Our total liability is limited to the fees you paid us in the 12 months preceding the claim.</p>

<h2>8. Indemnification</h2>
<p>You will indemnify and hold harmless Dream Easy LLC from any claims arising out of your use of the service, your content, your failure to obtain consent, or your violation of these Terms or applicable law \u2014 including carrier fines and TCPA claims.</p>

<h2>9. Governing law</h2>
<p>These Terms are governed by the laws of the State of Delaware, USA, without regard to conflict-of-laws principles. Disputes will be resolved in the state or federal courts located in New Castle County, Delaware.</p>

<h2>10. Changes</h2>
<p>We may update these Terms from time to time. Material changes will be communicated by email. Continued use after the effective date constitutes acceptance.</p>

<h2>11. Contact</h2>
<p>Dream Easy LLC \u2014 <a href="mailto:{legal_email}">{legal_email}</a>.</p>
""".format(legal_email=LEGAL_EMAIL)


SMS_POLICY_HTML = """
<div class="callout">
  This SMS Policy applies to all traffic sent through 2ndCall on US long-code (10DLC), toll-free, and short-code numbers. It supplements your approved campaign metadata at The Campaign Registry.
</div>

<h2>1. Consent</h2>
<p>You must obtain prior express written consent from every recipient before sending any SMS that is not explicitly in response to the recipient\u2019s own message. Consent must be collected in a way that:</p>
<ul>
  <li>Clearly identifies your business.</li>
  <li>States the types of messages the recipient will receive (e.g., \u201corder updates\u201d, \u201c2FA codes\u201d, \u201cmarketing\u201d).</li>
  <li>States the expected message frequency, that message and data rates may apply, and how to opt out.</li>
  <li>Is collected on a web form, printed form, SMS double-opt-in, or other documented channel \u2014 and is retained for at least 4 years.</li>
</ul>

<h2>2. Required message elements</h2>
<p>Your first message in every new conversation must include:</p>
<ol>
  <li>Your business name.</li>
  <li>Opt-out instructions (e.g., \u201cReply STOP to unsubscribe\u201d).</li>
  <li>For marketing campaigns, a clear reminder of how the recipient opted in.</li>
</ol>

<h2>3. Opt-out handling</h2>
<p>2ndCall automatically processes opt-out keywords on every inbound message. The following words (case-insensitive) mark a recipient as opted-out and block all further sends from your number to that recipient:</p>
<p><code>STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT, REVOKE, OPTOUT</code></p>
<p>The recipient receives an automatic confirmation. START / YES / UNSTOP re-subscribes them. HELP / INFO returns support contact info.</p>

<h2>4. Content restrictions</h2>
<p>The following is prohibited on 2ndCall and will result in immediate suspension:</p>
<ul>
  <li><strong>SHAFT content</strong>: sex, hate, alcohol, firearms, tobacco \u2014 unless you operate an explicitly approved age-gated campaign.</li>
  <li>Cannabis, CBD, kratom, and other controlled substances, regardless of state-level legality.</li>
  <li>Third-party lead generation and affiliate marketing where the sender does not have a direct relationship with the recipient.</li>
  <li>Payday loans, loan sharking, debt collection, debt consolidation outside of licensed collectors.</li>
  <li>Cryptocurrency solicitation, token airdrops, pump-and-dump campaigns.</li>
  <li>Gambling and sweepstakes outside of explicitly approved regulated operators.</li>
  <li>Phishing, smishing, credential harvesting, OTP interception, and impersonation of any brand.</li>
  <li>Any content that would violate the CTIA Messaging Principles and Best Practices, T-Mobile Code of Conduct, AT&amp;T Code of Conduct, or Verizon Messaging Policy.</li>
</ul>

<h2>5. Throughput and volume</h2>
<p>Sending throughput is scoped to your approved campaign. Attempting to exceed your tier, rotate sender numbers to evade filters (\u201csnowshoeing\u201d), or send from unregistered numbers is a violation that may result in account termination and carrier fines that we will pass through to you.</p>

<h2>6. Reporting abuse</h2>
<p>To report abusive traffic or a suspected phishing attempt, email <a href="mailto:{abuse_email}">{abuse_email}</a>. We triage within one business day and suspend confirmed abusers on sight.</p>
""".format(abuse_email=ABUSE_EMAIL)


AUP_HTML = """
<div class="callout">
  You must comply with this Acceptable Use Policy (\u201cAUP\u201d) in addition to our Terms of Service and SMS Policy. Violations can result in suspension without refund.
</div>

<h2>1. Prohibited uses</h2>
<ul>
  <li>Any activity that violates US federal, state, or local law, or the laws of the recipient\u2019s jurisdiction.</li>
  <li>Sending messages to recipients without the prior express consent required by the TCPA and applicable law.</li>
  <li>Operating an &quot;umbrella&quot; or multi-tenant sender on a single registered brand \u2014 each of your end-customers must register their own Brand + Campaign.</li>
  <li>Sending SHAFT content (sex, hate, alcohol, firearms, tobacco) outside of age-gated, carrier-approved campaigns.</li>
  <li>Promotion of illegal drugs or controlled substances, including cannabis, CBD, and kratom.</li>
  <li>Promotion of fraud, phishing, smishing, or any form of deception.</li>
  <li>Cryptocurrency solicitation, token airdrops, &quot;gray&quot; investment offers, or pump-and-dump schemes.</li>
  <li>Debt consolidation, payday loans, loan sharking, or debt collection outside of a licensed collector.</li>
  <li>Third-party lead generation or affiliate marketing where the sender does not have a direct prior relationship with the recipient.</li>
  <li>Harassment, stalking, doxxing, or transmission of threats.</li>
  <li>Transmission of malware, worms, trojans, or any code intended to harm.</li>
  <li>Attempts to probe, scan, or test the vulnerability of 2ndCall or to breach authentication controls.</li>
</ul>

<h2>2. Carrier rules</h2>
<p>You must comply with the current versions of:</p>
<ul>
  <li>CTIA Messaging Principles and Best Practices.</li>
  <li>T-Mobile Code of Conduct.</li>
  <li>AT&amp;T Code of Conduct.</li>
  <li>Verizon Messaging Policy.</li>
  <li>Bandwidth, Telnyx, Twilio, and SignalWire acceptable-use policies that apply to the downstream provider carrying your traffic.</li>
</ul>
<p>Where carrier rules change, the stricter rule controls.</p>

<h2>3. Enforcement</h2>
<p>Suspected violations may result in immediate suspension of messaging, voice, or both. We may report serious violations to carriers, to The Campaign Registry, to law enforcement, and to any affected third parties.</p>

<h2>4. Reporting</h2>
<p>Report suspected violations to <a href="mailto:{abuse_email}">{abuse_email}</a>.</p>
""".format(abuse_email=ABUSE_EMAIL)


DPA_HTML = """
<div class="callout">
  This Data Processing Addendum (\u201cDPA\u201d) forms part of the Terms of Service between you (\u201cController\u201d) and Dream Easy LLC (\u201cProcessor\u201d). It applies when you process personal data of individuals in the EEA, UK, or other jurisdictions requiring a DPA.
</div>

<h2>1. Subject matter</h2>
<p>We process personal data on your behalf solely to deliver the SMS and voice services under the Terms, including message transmission, delivery receipts, and regulatory compliance (e.g., A2P 10DLC registration).</p>

<h2>2. Subprocessors</h2>
<p>We use the following subprocessors:</p>
<ul>
  <li>Telnyx LLC (USA) \u2014 telephony.</li>
  <li>Twilio Inc. (USA) \u2014 telephony.</li>
  <li>SignalWire Inc. (USA) \u2014 telephony.</li>
  <li>Stripe, Inc. (USA) \u2014 payment processing.</li>
  <li>Railway Corp. (USA) \u2014 hosting.</li>
  <li>The Campaign Registry, Inc. (USA) \u2014 A2P brand / campaign registration.</li>
</ul>
<p>We will notify you by email at least 30 days before adding a new subprocessor. You may object and, if we cannot accommodate, terminate the affected service.</p>

<h2>3. Security measures</h2>
<p>TLS in transit, scrypt password hashing, least-privilege access, quarterly access reviews, and documented incident response. We will notify you of a confirmed personal data breach within 72 hours of becoming aware.</p>

<h2>4. International transfers</h2>
<p>Where personal data is transferred from the EEA or UK to the US, we rely on the applicable Standard Contractual Clauses (EU 2021/914) and UK International Data Transfer Addendum, which are incorporated by reference.</p>

<h2>5. Deletion</h2>
<p>On termination of the Terms, we will delete or return all personal data within 90 days, except where retention is required by law (telecom and tax record-keeping).</p>

<h2>6. Contact</h2>
<p>To request a counter-signed DPA on your paper, email <a href="mailto:{legal_email}">{legal_email}</a>.</p>
""".format(legal_email=LEGAL_EMAIL)


PAGES = {
    "privacy": ("Privacy Policy", PRIVACY_HTML),
    "terms": ("Terms of Service", TERMS_HTML),
    "sms-policy": ("SMS Policy", SMS_POLICY_HTML),
    "acceptable-use": ("Acceptable Use Policy", AUP_HTML),
    "dpa": ("Data Processing Addendum", DPA_HTML),
}
