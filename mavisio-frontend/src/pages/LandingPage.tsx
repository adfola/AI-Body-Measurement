import { ArrowRight, Check, Ruler, Scissors, ShieldCheck, Sparkles } from "lucide-react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/ui/button";

const features = [
  {
    icon: Ruler,
    title: "Thoughtful measurements",
    description: "Height-grounded estimates, organized in centimetres and inches.",
  },
  {
    icon: ShieldCheck,
    title: "Private client records",
    description: "Keep fitting histories together in your tailor workspace.",
  },
  {
    icon: Sparkles,
    title: "Guided camera capture",
    description: "Work through front and side views with live capture guidance.",
  },
];

export default function LandingPage() {
  const { token } = useAuth();

  if (token) return <Navigate to="/dashboard" replace />;

  return (
    <main className="landing-page">
      <header className="landing-nav">
        <Link to="/" className="landing-brand" aria-label="Mavisio home">
          <span className="brand-mark"><Scissors size={19} strokeWidth={1.8} /></span>
          <span><strong>MAVISIO</strong><small>MEASUREMENT STUDIO</small></span>
        </Link>
        <nav aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <Link to="/login">Sign in</Link>
          <Button asChild size="sm"><Link to="/login">Get started <ArrowRight size={15} /></Link></Button>
        </nav>
      </header>

      <section className="landing-hero">
        <div className="landing-copy">
          <span className="landing-kicker"><i /> A STUDIO FOR THE CRAFT OF FITTING</span>
          <h1>Fit begins with <em>understanding.</em></h1>
          <p>
            A calm, considered workspace for tailors to guide body measurements,
            care for client records, and return to every fitting with confidence.
          </p>
          <div className="landing-actions">
            <Button asChild size="lg"><Link to="/login">Open your studio <ArrowRight size={17} /></Link></Button>
            <Link className="landing-secondary-link" to="/login">Already have an account? Sign in</Link>
          </div>
          <div className="landing-assurance"><Check size={15} /> Your client records stay private to your account</div>
        </div>

        <div className="landing-art" aria-label="A preview of the measurement workflow">
          <div className="landing-art-top"><span>THE FITTING ROOM</span><span><i /> READY WHEN YOU ARE</span></div>
          <div className="landing-art-content">
            <div className="landing-art-intro">
              <span className="section-index">A MORE CONSIDERED FIT</span>
              <h2>From first measure<br />to lasting record.</h2>
            </div>
            <div className="landing-workflow">
              <div className="workflow-mark"><Ruler size={18} /></div>
              <div><strong>Front view</strong><span>Set a steady starting point</span></div>
              <Check size={16} />
            </div>
            <div className="workflow-connector" />
            <div className="landing-workflow">
              <div className="workflow-mark"><Scissors size={18} /></div>
              <div><strong>Side view</strong><span>Build a fuller measurement picture</span></div>
              <Check size={16} />
            </div>
            <div className="workflow-connector" />
            <div className="landing-record">
              <div><span className="section-index">CLIENT RECORD</span><strong>Measurements, together</strong></div>
              <span className="record-units">CM <i /> IN</span>
            </div>
          </div>
          <div className="landing-art-bottom"><span>PERSONAL · PRACTICAL · PRIVATE</span><span>01 — 03</span></div>
        </div>
      </section>

      <section className="landing-features" id="how-it-works">
        <div className="landing-features-heading">
          <span className="section-index">MADE FOR THE WORKSHOP</span>
          <h2>Every fitting, a little more considered.</h2>
        </div>
        <div className="landing-feature-grid">
          {features.map(({ icon: Icon, title, description }, index) => (
            <article className="landing-feature" key={title}>
              <span className="landing-feature-number">0{index + 1}</span>
              <Icon size={19} />
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <span>MAVISIO <i /> MEASUREMENT STUDIO</span>
        <span>Camera-derived measurements are estimates. Validate before garment production.</span>
      </footer>
    </main>
  );
}
