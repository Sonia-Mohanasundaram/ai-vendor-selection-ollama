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
            Upload PDFs, spreadsheets and quotation images. We extract, normalize and compare across cost,
            delivery and payment terms — then tell you exactly why one vendor wins.
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
          <div className="mt-16 grid grid-cols-3 gap-8 max-w-2xl mx-auto text-left">
            {[
              { v: "10x", l: "faster procurement" },
              { v: "95%", l: "extraction accuracy" },
              { v: "₹2.4L", l: "avg. savings / RFQ" },
            ].map((s) => (
              <div key={s.l} className="glass rounded-2xl p-4 shadow-card">
                <div className="text-2xl md:text-3xl font-bold text-gradient">{s.v}</div>
                <div className="text-xs text-muted-foreground mt-1">{s.l}</div>
              </div>
            ))}
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
              { icon: BarChart3, title: "Vendor Comparison", desc: "Side-by-side scoring across price, GST, freight and terms.", grad: "from-blue-500 to-cyan-500" },
              { icon: Wallet, title: "Cost Intelligence", desc: "Includes credit cost so payment terms become real money.", grad: "from-violet-500 to-purple-500" },
              { icon: Zap, title: "Fast Processing", desc: "Drop 10 quotes — get a recommendation in seconds.", grad: "from-amber-500 to-orange-500" },
              { icon: FileStack, title: "Multi-format Upload", desc: "PDF, image, CSV, Excel — we handle the messy ones too.", grad: "from-emerald-500 to-teal-500" },
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
            <p className="text-muted-foreground text-lg">No setup. No training data. Just drop and go.</p>
          </div>
          <div className="grid md:grid-cols-4 gap-6">
            {[
              { icon: Upload, title: "Upload files", desc: "Drag 3–10 vendor quotations." },
              { icon: Layers, title: "Extract data", desc: "OCR + parsers pull line items, taxes and terms." },
              { icon: TrendingUp, title: "Compare vendors", desc: "Weighted scoring across cost, delivery and terms." },
              { icon: Trophy, title: "Get the winner", desc: "A clear recommendation with plain-English reasoning." },
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
            <h2 className="text-4xl font-bold mb-4">A taste of the output</h2>
            <p className="text-muted-foreground text-lg">Cost-normalized, term-adjusted, decision-ready.</p>
          </div>
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 rounded-2xl bg-card border shadow-elevated overflow-hidden">
              <div className="px-5 py-3 border-b bg-muted/40 text-sm font-medium">Vendor comparison</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/30 text-muted-foreground">
                    <tr>
                      {["Vendor","Total (INR)","Delivery","Payment","Score"].map((h) => (
                        <th key={h} className="text-left px-4 py-2 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { v: "Acme Industrial", t: "2,18,400", d: "12d", p: "Net 45", s: "94%", best: true },
                      { v: "Bharat Supplies", t: "2,32,100", d: "10d", p: "Net 30", s: "88%" },
                      { v: "Crown Vendors",  t: "2,46,800", d: "18d", p: "Net 60", s: "79%" },
                    ].map((r) => (
                      <tr key={r.v} className="border-t">
                        <td className="px-4 py-3 font-medium">
                          {r.v}
                          {r.best && <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-gold/20 text-gold-foreground">Winner</span>}
                        </td>
                        <td className="px-4 py-3 text-success font-medium">₹{r.t}</td>
                        <td className="px-4 py-3 text-info">{r.d}</td>
                        <td className="px-4 py-3">{r.p}</td>
                        <td className="px-4 py-3 font-semibold">{r.s}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="rounded-2xl p-6 gradient-primary text-primary-foreground shadow-elevated">
              <Trophy className="h-8 w-8 mb-3" />
              <div className="text-sm uppercase tracking-wider opacity-80">Recommended</div>
              <div className="text-2xl font-bold mt-1">Acme Industrial</div>
              <div className="text-sm opacity-90 mt-3">
                Lowest total cost after credit-cost adjustment, delivery only 2 days slower than the fastest, and 45-day payment terms boost cash flow.
              </div>
              <div className="mt-6 grid grid-cols-3 gap-2 text-center">
                {[{l:"Score",v:"94%"},{l:"Rank",v:"#1"},{l:"Save",v:"₹14k"}].map((x) => (
                  <div key={x.l} className="bg-white/10 rounded-xl py-2">
                    <div className="text-lg font-bold">{x.v}</div>
                    <div className="text-[10px] uppercase opacity-80">{x.l}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Trust */}
      <section className="py-20">
        <div className="container grid md:grid-cols-3 gap-6">
          {[
            { i: Shield, t: "Local-first", d: "Files are processed in-browser by default." },
            { i: Clock, t: "Auditable", d: "Every score has a transparent formula behind it." },
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
