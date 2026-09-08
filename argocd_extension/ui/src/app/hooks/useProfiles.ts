import { apiJson } from "../../api/client";
import { errMsg, paginatedQuery } from "../../lib/format";
import { emptyProfileForm, profilePayload, profileToForm } from "../../lib/profiles";
import type { ProfileForm, ProfileSubview } from "../../lib/types";
import type { AppMessages } from "./useAppMessages";
import type { GoFn } from "./useAppRouting";

type UseProfilesArgs = {
  tab: string;
  profileSubview: ProfileSubview;
  go: GoFn;
  messages: AppMessages;
  onProfilesChanged?: () => void | Promise<void>;
};

export function useProfiles({ tab, profileSubview, go, messages, onProfilesChanged }: UseProfilesArgs) {
  const { setError, setFlash } = messages;
  const [profileItems, setProfileItems] = React.useState<any[]>([]);
  const [profileTotal, setProfileTotal] = React.useState(0);
  const [profilePage, setProfilePage] = React.useState(0);
  const [profileLoading, setProfileLoading] = React.useState(false);
  const [profileForm, setProfileForm] = React.useState<ProfileForm>(emptyProfileForm());
  const [profileFormReady, setProfileFormReady] = React.useState(profileSubview !== "edit");
  const [profileSubmitting, setProfileSubmitting] = React.useState(false);
  const listLoadSeqRef = React.useRef(0);
  const editLoadSeqRef = React.useRef(0);

  const resetProfileForm = React.useCallback(() => {
    editLoadSeqRef.current += 1;
    setProfileForm(emptyProfileForm());
    setProfileFormReady(true);
  }, []);

  const loadProfileList = React.useCallback(
    async ({ quiet = false, page: pageOverride }: { quiet?: boolean; page?: number } = {}) => {
      const seq = ++listLoadSeqRef.current;
      const p = pageOverride ?? profilePage;
      if (!quiet) setProfileLoading(true);
      try {
        const data = (await apiJson(`/profiles?${paginatedQuery(p)}`)) as any;
        if (seq !== listLoadSeqRef.current) return;
        setProfileItems(data.items || []);
        setProfileTotal(data.total || 0);
        if (pageOverride != null) setProfilePage(pageOverride);
        if (!quiet) setError("");
      } catch (e) {
        if (seq !== listLoadSeqRef.current) return;
        if (!quiet) setError(errMsg(e));
      } finally {
        if (seq === listLoadSeqRef.current && !quiet) setProfileLoading(false);
      }
    },
    [profilePage, setError],
  );

  const loadProfileForEdit = React.useCallback(
    async (id: string): Promise<boolean> => {
      const seq = ++editLoadSeqRef.current;
      setError("");
      setProfileFormReady(false);
      try {
        const profile = await apiJson(`/profiles/${id}`);
        if (seq !== editLoadSeqRef.current) return false;
        setProfileForm(profileToForm(profile));
        setProfileFormReady(true);
        return true;
      } catch (e) {
        if (seq !== editLoadSeqRef.current) return false;
        setError(errMsg(e));
        setProfileFormReady(true);
        return false;
      }
    },
    [setError],
  );

  const openProfileEdit = React.useCallback(
    async (id: string) => {
      go({ tab: "profiles", profileSubview: "edit", profileId: id });
      await loadProfileForEdit(id);
    },
    [go, loadProfileForEdit],
  );

  const submitProfile = React.useCallback(
    async (mode: "create" | "edit") => {
      setProfileSubmitting(true);
      setError("");
      try {
        const payload = profilePayload(profileForm, mode);
        if (mode === "create") {
          await apiJson("/profiles", { method: "POST", body: JSON.stringify(payload) });
          setFlash("Profile created");
          setProfileForm(emptyProfileForm());
          go({ tab: "profiles", profileSubview: "list" });
          await loadProfileList({ page: 0 });
          await onProfilesChanged?.();
        } else {
          await apiJson(`/profiles/${profileForm.id}`, { method: "PUT", body: JSON.stringify(payload) });
          setFlash("Profile updated");
          go({ tab: "profiles", profileSubview: "list" });
          await loadProfileList();
          await onProfilesChanged?.();
        }
      } catch (e) {
        setError(errMsg(e));
      } finally {
        setProfileSubmitting(false);
      }
    },
    [go, loadProfileList, onProfilesChanged, profileForm, setError, setFlash],
  );

  const deleteProfile = React.useCallback(
    async (id: string) => {
      if (!window.confirm(`Delete profile "${id}"? Existing runs keep this profile id but retry may not work.`)) return;
      setError("");
      try {
        await apiJson(`/profiles/${id}`, { method: "DELETE" });
        setFlash("Profile deleted");
        await loadProfileList();
        await onProfilesChanged?.();
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [loadProfileList, onProfilesChanged, setError, setFlash],
  );

  React.useEffect(() => {
    if (tab === "profiles" && profileSubview === "list") loadProfileList();
  }, [tab, profileSubview, loadProfileList]);

  return {
    profileItems,
    profileTotal,
    profilePage,
    profileLoading,
    profileForm,
    profileFormReady,
    profileSubmitting,
    setProfilePage,
    setProfileForm,
    resetProfileForm,
    loadProfileList,
    loadProfileForEdit,
    openProfileEdit,
    submitProfile,
    deleteProfile,
  };
}

export type ProfilesState = ReturnType<typeof useProfiles>;
