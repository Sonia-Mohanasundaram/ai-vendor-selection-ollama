import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  ArrowRight, BarChart3, Wallet, Zap, FileStack, Upload, Sparkles,
  CheckCircle2, Trophy, TrendingUp, Layers, Shield, Clock,
} from "lucide-react";

const Landing = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 glass border-b">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-xl gradient-primary flex items-center justify-center shadow-glow">
              <Sparkles className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="font-bold text-lg">QuoteIQ</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-muted-foreground">
            <a href="#features" className="hover:text-foreground transition">Features</a>
            <a href="#how" className="hover:text-foreground transition">How it works</a>
            <a href="#sample" className="hover:text-foreground transition">Sample</a>
          </div>
          <Link to="/dashboard">
            <Button className="gradient-primary text-primary-foreground border-0 shadow-glow hover:opacity-90">
              Launch App
            </Button>
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-24 overflow-hidden">
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-20 left-10 w-96 h-96 bg-primary/30 rounded-full blur-3xl animate-blob" />
          <div className="absolute top-40 right-10 w-96 h-96 bg-secondary/30 rounded-full blur-3xl animate-blob" style={{ animationDelay: "3s" }} />
          <div className="absolute bottom-0 left-1/3 w-96 h-96 bg-info/20 rounded-full blur-3xl animate-blob" style={{ animationDelay: "6s" }} />
        </div>
        <div className="container text-center max-w-4xl">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent text-accent-foreground text-sm font-medium mb-6">
            <Sparkles className="h-3.5 w-3.5" />
            AI-Powered Procurement Intelligence
          </div>
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
            Pick the <span className="text-gradient">right vendor</span><br />
            in 30 seconds.
          </h1>
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
            Upload quotations, describe your priorities, and get a local AI comparison of extracted cost,
            delivery and payment evidence — including missing details and uncertainty.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link to="/dashboard">
              <Button size="lg" className="gradient-primary text-primary-foreground border-0 shadow-glow hover:opacity-90 h-12 px-8 text-base">
                🚀 Get Started <ArrowRight className="ml-2" />
              </Button>
            </Link>
            <a href="#sample">
              <Button size="lg" variant="outline" className="h-12 px-8 text-base">
                See sample analysis
              </Button>
            </a>
          </div>
          <div className="mt-12 text-sm text-muted-foreground">
            Local Ollama model · Evidence-based explanations · No paid AI API
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 bg-muted/30">
        <div className="container">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-4xl font-bold mb-4">Everything you need to decide</h2>
            <p className="text-muted-foreground text-lg">Procurement-grade intelligence, in a beautiful interface.</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: BarChart3, title: "Requirement-led comparison", desc: "The local model adapts its qualitative evaluation to your priorities.", grad: "from-blue-500 to-cyan-500" },
              { icon: Wallet, title: "Verified quotation totals", desc: "Known base price, GST and freight are calculated deterministically; unknown charges stay unknown.", grad: "from-violet-500 to-purple-500" },
              { icon: Zap, title: "Transparent trade-offs", desc: "Review each vendor's advantages, drawbacks, risks and confidence.", grad: "from-amber-500 to-orange-500" },
              { icon: FileStack, title: "Multi-format upload", desc: "Extract quotation data from PDF, image, CSV and Excel files.", grad: "from-emerald-500 to-teal-500" },
            ].map((f) => (
              <div key={f.title} className="group rounded-2xl p-6 bg-card border shadow-card hover:shadow-elevated transition">
                <div className={`h-12 w-12 rounded-xl bg-gradient-to-br ${f.grad} flex items-center justify-center mb-4 shadow-glow group-hover:scale-110 transition`}>
                  <f.icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
                <p className="text-sm text-muted-foreground">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="py-24">
        <div className="container">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-4xl font-bold mb-4">From PDF to decision in 4 steps</h2>
            <p className="text-muted-foreground text-lg">Run Ollama locally, upload quotations, then review the evidence.</p>
          </div>
          <div className="grid md:grid-cols-4 gap-6">
            {[
              { icon: Upload, title: "Upload files", desc: "Add 2–10 vendor quotations and state your priorities." },
              { icon: Layers, title: "Extract evidence", desc: "Existing PDF, table and OCR parsers collect quotation details." },
              { icon: TrendingUp, title: "Evaluate locally", desc: "Ollama compares the extracted data against your requirements." },
              { icon: Trophy, title: "Review the result", desc: "See rankings, risks, missing fields or an inconclusive outcome." },
            ].map((s, i) => (
              <div key={s.title} className="relative rounded-2xl p-6 bg-card border shadow-card">
                <div className="absolute -top-4 -left-4 h-10 w-10 rounded-xl gradient-primary flex items-center justify-center text-primary-foreground font-bold shadow-glow">
                  {i + 1}
                </div>
                <s.icon className="h-8 w-8 text-primary mb-4" />
                <h3 className="font-semibold text-lg mb-2">{s.title}</h3>
                <p className="text-sm text-muted-foreground">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Sample output */}
      <section id="sample" className="py-24 bg-muted/30">
        <div className="container">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-4xl font-bold mb-4">What an evaluation includes</h2>
            <p className="text-muted-foreground text-lg">Results are generated from your uploaded quotations—not from a fabricated sample ranking.</p>
          </div>
          <div className="grid lg:grid-cols-3 gap-6">
            {[
              { icon: Trophy, title: "Recommendation or inconclusive result", description: "The model may abstain when quotation evidence is incomplete or does not support a reliable winner." },
              { icon: BarChart3, title: "Vendor-by-vendor reasoning", description: "Compare cost, delivery and payment terms with advantages, disadvantages and risks." },
              { icon: Shield, title: "Evidence and uncertainty", description: "See extracted values, missing information, extraction warnings and confidence limitations." },
            ].map((item) => (
              <div key={item.title} className="rounded-2xl p-6 bg-card border shadow-card">
                <item.icon className="h-8 w-8 text-primary mb-4" />
                <h3 className="font-semibold text-lg mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Trust */}
      <section className="py-20">
        <div className="container grid md:grid-cols-3 gap-6">
          {[
            { i: Shield, t: "Local-first", d: "The backend sends structured quotation data to your local Ollama service." },
            { i: Clock, t: "Auditable", d: "Displayed numeric values come from extracted fields and deterministic calculations." },
            { i: CheckCircle2, t: "Decision-ready", d: "Plain-English explanations for every recommendation." },
          ].map((x) => (
            <div key={x.t} className="rounded-2xl p-6 border bg-card shadow-card flex gap-4">
              <div className="h-12 w-12 rounded-xl bg-accent flex items-center justify-center shrink-0">
                <x.i className="h-6 w-6 text-accent-foreground" />
              </div>
              <div>
                <div className="font-semibold">{x.t}</div>
                <div className="text-sm text-muted-foreground">{x.d}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="container">
          <div className="rounded-3xl gradient-hero p-12 md:p-20 text-center text-primary-foreground shadow-elevated relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,white_0%,transparent_60%)] opacity-20" />
            <div className="relative">
              <h2 className="text-4xl md:text-5xl font-bold mb-4">Start your analysis</h2>
              <p className="text-lg opacity-90 max-w-xl mx-auto mb-8">
                Drop your first batch of vendor quotations and get a recommendation in under a minute.
              </p>
              <Link to="/dashboard">
                <Button size="lg" className="bg-white text-primary hover:bg-white/90 h-12 px-8 text-base">
                  Open Dashboard <ArrowRight className="ml-2" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t py-8 text-center text-sm text-muted-foreground">
        QuoteIQ • AI-powered procurement intelligence
      </footer>
    </div>
  );
};

export default Landing;
