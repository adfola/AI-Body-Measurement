import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ArrowUpRight, Clock3, Plus, Ruler, Search, Trash2, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import AlertMessage from "../components/AlertMessage";
import LoadingState from "../components/LoadingState";
import PageHeading from "../components/PageHeading";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import type { Customer } from "../types";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [name, setName] = useState("");
  const [height, setHeight] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.customers().then(setCustomers).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "Could not load customers.");
    }).finally(() => setLoading(false));
  }, []);

  const visibleCustomers = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return customers.filter((customer) => customer.full_name.toLocaleLowerCase().includes(query));
  }, [customers, search]);

  async function addCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const customer = await api.createCustomer({ full_name: name.trim(), height_cm: Number(height) });
      setCustomers((current) => [customer, ...current]);
      setName("");
      setHeight("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add customer.");
    } finally {
      setSaving(false);
    }
  }

  async function removeCustomer(customer: Customer) {
    if (!window.confirm(`Delete ${customer.full_name} and all saved measurement sessions?`)) return;
    try {
      await api.deleteCustomer(customer.id);
      setCustomers((current) => current.filter((item) => item.id !== customer.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete customer.");
    }
  }

  return (
    <div className="page-stack">
      <PageHeading eyebrow="CLIENT DIRECTORY" title="Your clients" description="A considered record of every fitting, ready when you are." action={<Badge className="count-badge"><UsersRound size={13} /> {customers.length} {customers.length === 1 ? "client" : "clients"}</Badge>} />
      {error && <AlertMessage>{error}</AlertMessage>}
      <div className="customer-layout">
        <Card className="add-customer-card">
          <CardHeader><div className="section-index">01 / NEW RECORD</div><CardTitle>Add a client</CardTitle><p className="card-note">Height helps calibrate every measurement.</p></CardHeader>
          <CardContent>
            <form onSubmit={addCustomer} className="customer-form">
              <label htmlFor="full-name">Full name</label>
              <Input id="full-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Amara Okafor" maxLength={120} required />
              <label htmlFor="height-cm">Height <span>CM</span></label>
              <div className="input-with-unit"><Input id="height-cm" type="number" min={100} max={230} step={0.1} value={height} onChange={(event) => setHeight(event.target.value)} placeholder="165" required /><span>cm</span></div>
              <Button type="submit" className="add-client-button" disabled={saving}><Plus size={17} /> {saving ? "Adding client..." : "Add client"}</Button>
            </form>
          </CardContent>
        </Card>
        <section className="client-section">
          <div className="client-toolbar">
            <div><div className="section-index">02 / DIRECTORY</div><h2>Recent clients</h2></div>
            <label className="search-box"><Search size={16} /><Input aria-label="Search clients" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a client" /></label>
          </div>
          {loading ? <LoadingState label="Loading client records" /> : visibleCustomers.length ? (
            <div className="client-list">
              {visibleCustomers.map((customer, index) => (
                <article className="client-row" key={customer.id}>
                  <div className="client-number">{String(index + 1).padStart(2, "0")}</div>
                  <div className="client-avatar">{customer.full_name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</div>
                  <div className="client-identity"><strong>{customer.full_name}</strong><span><Ruler size={13} /> {customer.height_cm ?? "Height needed"} {customer.height_cm ? "cm" : ""}</span></div>
                  <div className="client-date"><Clock3 size={13} /> {new Date(customer.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div>
                  <div className="client-actions">
                    <Button asChild size="sm"><Link to={`/measure/${customer.id}`}><Ruler size={14} /> Measure</Link></Button>
                    <Button asChild variant="outline" size="sm" aria-label={`View ${customer.full_name} history`}><Link to={`/history/${customer.id}`}><ArrowUpRight size={15} /></Link></Button>
                    <Button variant="ghost" size="icon" className="delete-button" aria-label={`Delete ${customer.full_name}`} onClick={() => removeCustomer(customer)}><Trash2 size={15} /></Button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-clients"><span className="empty-mark"><UsersRound size={23} /></span><strong>{search ? "No matching clients" : "Your directory is ready"}</strong><p>{search ? "Try another name." : "Add your first client to begin a measurement record."}</p></div>
          )}
        </section>
      </div>
      <div className="privacy-strip"><span className="privacy-mark" /> Client records are private to your tailor account <span className="privacy-spacer" /> CUSTOMER DATA · OWNER-SCOPED</div>
    </div>
  );
}
