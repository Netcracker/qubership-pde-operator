import { apiJson } from "../../api/client";
import { errMsg, paginatedQuery } from "../../lib/format";
import { emptyTemplateForm, templatePayload, templateToForm } from "../../lib/templates";
import type { CatalogSubview, TemplateForm } from "../../lib/types";
import type { AppMessages } from "./useAppMessages";
import type { GoFn } from "./useAppRouting";
import { getHost } from "../../host/registry";

type UseCatalogArgs = {
  tab: string;
  catalogSubview: CatalogSubview;
  go: GoFn;
  messages: AppMessages;
};

export function useCatalog({ tab, catalogSubview, go, messages }: UseCatalogArgs) {
  const { setError, setFlash } = messages;
  const [items, setItems] = React.useState<any[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(0);
  const [query, setQuery] = React.useState("");
  const [tagFilter, setTagFilter] = React.useState("");
  const [debouncedQuery, setDebouncedQuery] = React.useState("");
  const [debouncedTag, setDebouncedTag] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [templateForm, setTemplateForm] = React.useState<TemplateForm>(emptyTemplateForm());
  const [submitting, setSubmitting] = React.useState(false);
  const [uploadingDeclarative, setUploadingDeclarative] = React.useState(false);
  const [profiles, setProfiles] = React.useState<any[]>([]);
  const [formReady, setFormReady] = React.useState(catalogSubview !== "edit");
  const listLoadSeqRef = React.useRef(0);
  const editLoadSeqRef = React.useRef(0);
  const listFilterRef = React.useRef({ q: debouncedQuery, tag: debouncedTag });

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 250);
    return () => clearTimeout(t);
  }, [query]);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedTag(tagFilter), 250);
    return () => clearTimeout(t);
  }, [tagFilter]);

  const resetTemplateForm = React.useCallback(() => {
    editLoadSeqRef.current += 1;
    setTemplateForm(emptyTemplateForm());
    setFormReady(true);
  }, []);

  const loadProfiles = React.useCallback(async () => {
    try {
      const data = (await apiJson("/profiles?limit=500")) as any;
      setProfiles(data.items || []);
    } catch {
      setProfiles([]);
    }
  }, []);

  const loadList = React.useCallback(
    async ({ quiet = false, page: pageOverride }: { quiet?: boolean; page?: number } = {}) => {
      const seq = ++listLoadSeqRef.current;
      const p = pageOverride ?? page;
      if (!quiet) setLoading(true);
      try {
        const params = paginatedQuery(p);
        if (debouncedQuery.trim()) params.set("q", debouncedQuery.trim());
        if (debouncedTag.trim()) params.set("tag", debouncedTag.trim());
        const data = (await apiJson(`/run-templates?${params}`)) as any;
        if (seq !== listLoadSeqRef.current) return;
        setItems(data.items || []);
        setTotal(data.total || 0);
        if (pageOverride != null) setPage(pageOverride);
        if (!quiet) setError("");
      } catch (e) {
        if (seq !== listLoadSeqRef.current) return;
        if (!quiet) setError(errMsg(e));
      } finally {
        if (seq === listLoadSeqRef.current && !quiet) setLoading(false);
      }
    },
    [debouncedQuery, debouncedTag, page, setError],
  );

  const loadForEdit = React.useCallback(
    async (id: string): Promise<boolean> => {
      const seq = ++editLoadSeqRef.current;
      setError("");
      setFormReady(false);
      try {
        await loadProfiles();
        const template = await apiJson(`/run-templates/${id}`);
        if (seq !== editLoadSeqRef.current) return false;
        setTemplateForm(templateToForm(template));
        setFormReady(true);
        return true;
      } catch (e) {
        if (seq !== editLoadSeqRef.current) return false;
        setError(errMsg(e));
        setFormReady(true);
        return false;
      }
    },
    [loadProfiles, setError],
  );

  const openEdit = React.useCallback(
    async (id: string) => {
      if (await loadForEdit(id)) go({ tab: "catalog", catalogSubview: "edit", catalogId: id });
    },
    [go, loadForEdit],
  );

  const openCreateRun = React.useCallback(
    (id: string) => {
      go({ tab: "create", createMode: "create", templateId: id });
    },
    [go],
  );

  const openHistory = React.useCallback(
    (templateId: string) => {
      go({ tab: "list", templateId });
    },
    [go],
  );

  const submitTemplate = React.useCallback(
    async (mode: "create" | "edit") => {
      setSubmitting(true);
      setError("");
      try {
        const payload = templatePayload(templateForm);
        if (mode === "create") {
          await apiJson("/run-templates", { method: "POST", body: JSON.stringify(payload) });
          setFlash("Template created");
          setTemplateForm(emptyTemplateForm());
          go({ tab: "catalog", catalogSubview: "list" });
          await loadList({ page: 0 });
        } else {
          await apiJson(`/run-templates/${templateForm.id}`, { method: "PUT", body: JSON.stringify(payload) });
          setFlash("Template updated");
          go({ tab: "catalog", catalogSubview: "list" });
          await loadList();
        }
      } catch (e) {
        setError(errMsg(e));
      } finally {
        setSubmitting(false);
      }
    },
    [go, loadList, setError, setFlash, templateForm],
  );

  const deleteTemplate = React.useCallback(
    async (id: string, name?: string) => {
      const label = name || id;
      if (!window.confirm(`Delete run template "${label}"?`)) return;
      setError("");
      try {
        await apiJson(`/run-templates/${id}`, { method: "DELETE" });
        setFlash("Template deleted");
        await loadList();
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [loadList, setError, setFlash],
  );

  const uploadDeclarativeTemplate = React.useCallback(
    async (file: File) => {
      setUploadingDeclarative(true);
      setError("");
      try {
        const host = getHost();
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${host.apiBase}/run-templates/declarative/upload`, {
          method: "POST",
          headers: host.authHeaders(),
          credentials: host.credentials,
          body: formData,
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `Upload failed (${res.status})`);
        }

        setFlash("Declarative template uploaded");
        await loadList({ page: 0, quiet: true });
      } catch (e) {
        setError(errMsg(e));
      } finally {
        setUploadingDeclarative(false);
      }
    },
    [loadList, setError, setFlash],
  );

  React.useEffect(() => {
    if (tab !== "catalog" || catalogSubview !== "list") return;
    const prev = listFilterRef.current;
    const filterChanged = prev.q !== debouncedQuery || prev.tag !== debouncedTag;
    listFilterRef.current = { q: debouncedQuery, tag: debouncedTag };
    if (filterChanged) {
      setPage(0);
      void loadList({ page: 0 });
      return;
    }
    void loadList();
  }, [tab, catalogSubview, page, debouncedQuery, debouncedTag, loadList]);

  React.useEffect(() => {
    if (tab === "catalog" && (catalogSubview === "create" || catalogSubview === "edit")) {
      void loadProfiles();
    }
  }, [tab, catalogSubview, loadProfiles]);

  return {
    items,
    total,
    page,
    loading,
    formReady,
    query,
    tagFilter,
    templateForm,
    submitting,
    profiles,
    setPage,
    setQuery,
    setTagFilter,
    setTemplateForm,
    resetTemplateForm,
    loadList,
    loadForEdit,
    openEdit,
    openCreateRun,
    openHistory,
    submitTemplate,
    deleteTemplate,
    uploadingDeclarative,
    uploadDeclarativeTemplate,
  };
}

export type CatalogState = ReturnType<typeof useCatalog>;
