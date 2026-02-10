import { useEffect, useMemo, useState } from "react";

import { getCatalog } from "../api/catalog";
import { RU, formatCurrencyRub, formatDateRu } from "../i18n/ru";
import EmptyState from "../components/EmptyState";
import SkeletonCard from "../components/SkeletonCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import Input from "../components/ui/Input";
import { Table, TBody, TD, TH, THead, TR } from "../components/ui/Table";

const typeLabel = (value) => {
  if (value === "course") return RU.labels.catalogCourses;
  if (value === "product") return RU.labels.catalogProducts;
  return RU.messages.notSet;
};

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setLoading(true);
        setError("");
        const data = await getCatalog({ limit: 200 });
        if (!active) return;
        setItems(data.items ?? []);
      } catch (err) {
        if (!active) return;
        setError(err?.message || RU.messages.dataLoadError);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((item) => {
      if (typeFilter !== "all" && item.item_type !== typeFilter) return false;
      if (!normalizedQuery) return true;
      const haystack = [item.title, item.description].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [items, query, typeFilter]);

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold">{RU.labels.catalogTitle}</h2>
          <p className="text-sm text-slate-500">{RU.labels.catalogSubtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={RU.labels.catalogSearch}
            className="min-w-[260px]"
          />

          <select
            className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="all">{RU.labels.catalogAllTypes}</option>
            <option value="course">{RU.labels.catalogCourses}</option>
            <option value="product">{RU.labels.catalogProducts}</option>
          </select>
        </div>
      </CardHeader>

      <CardContent>
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <SkeletonCard rows={4} className="p-6" />
        ) : filteredItems.length === 0 ? (
          <EmptyState title={RU.labels.catalogEmpty} description={RU.labels.catalogEmptyHint} />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>{RU.labels.name}</TH>
                <TH>{RU.labels.catalogType}</TH>
                <TH>{RU.labels.price}</TH>
                <TH>{RU.labels.status}</TH>
                <TH>{RU.labels.catalogUpdatedAt}</TH>
                <TH className="text-right">{RU.labels.actions}</TH>
              </TR>
            </THead>
            <TBody>
              {filteredItems.map((item) => (
                <TR key={item.id}>
                  <TD>
                    <div className="font-medium text-slate-900">{item.title}</div>
                    <div className="line-clamp-2 text-xs text-slate-500">{item.description || RU.messages.notSet}</div>
                  </TD>
                  <TD>{typeLabel(item.item_type)}</TD>
                  <TD>{item.price ? formatCurrencyRub(item.price) : RU.messages.notSet}</TD>
                  <TD>
                    <Badge variant={item.status === "active" ? "active" : "finished"}>
                      {item.status === "active" ? RU.statuses.active : RU.statuses.archived}
                    </Badge>
                  </TD>
                  <TD>{formatDateRu(item.updated_at, { dateStyle: "short", timeStyle: "short" })}</TD>
                  <TD className="text-right">
                    {item.link_getcourse ? (
                      <a href={item.link_getcourse} target="_blank" rel="noreferrer">
                        <Button variant="secondary">{RU.buttons.open}</Button>
                      </a>
                    ) : (
                      <span className="text-xs text-slate-400">{RU.messages.notSet}</span>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
