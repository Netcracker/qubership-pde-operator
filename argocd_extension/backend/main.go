package main

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	headerArgoUsername = "Argocd-Username"
	headerArgoGroups   = "Argocd-User-Groups"
)

type rbacConfig struct {
	writeUsers  map[string]struct{}
	writeGroups map[string]struct{}
}

func main() {
	operatorBase := strings.TrimRight(envOrDefault("PDE_OPERATOR_BASE_URL", "http://pde-operator.pde-system.svc:8000"), "/")
	operatorToken := strings.TrimSpace(os.Getenv("PDE_OPERATOR_API_TOKEN"))
	listenAddr := envOrDefault("LISTEN_ADDR", ":8081")
	rbac := loadRBAC()

	client := &http.Client{Timeout: 60 * time.Second}

	mux := http.NewServeMux()

	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})

	mux.HandleFunc("/capabilities", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			http.Error(w, `{"detail":"method_not_allowed"}`, http.StatusMethodNotAllowed)
			return
		}
		username := strings.TrimSpace(r.Header.Get(headerArgoUsername))
		payload, _ := json.Marshal(map[string]any{
			"canWrite": rbac.isWriter(r),
			"username": username,
		})
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if r.Method != http.MethodHead {
			_, _ = w.Write(payload)
		}
	})

	// Pass-through: /<path>?q=... -> <operator>/api/v1/<path>?q=...
	// Argo proxy strips /extensions/<name> before forwarding.
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if !isSafeMethod(r.Method) && !rbac.isWriter(r) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusForbidden)
			_, _ = w.Write([]byte(`{"detail":"write_forbidden"}`))
			return
		}

		path := r.URL.Path
		if path == "" {
			path = "/"
		}
		targetURL := operatorBase + "/api/v1" + path
		if r.URL.RawQuery != "" {
			targetURL += "?" + r.URL.RawQuery
		}

		req, err := http.NewRequestWithContext(r.Context(), r.Method, targetURL, r.Body)
		if err != nil {
			http.Error(w, `{"detail":"failed to build request"}`, http.StatusInternalServerError)
			return
		}
		req.Header = r.Header.Clone()
		req.Header.Del("Cookie")
		req.Header.Del("Authorization")
		if operatorToken != "" {
			req.Header.Set("Authorization", "Bearer "+operatorToken)
		}

		resp, err := client.Do(req)
		if err != nil {
			http.Error(w, `{"detail":"operator_unreachable"}`, http.StatusBadGateway)
			return
		}
		defer func() { _ = resp.Body.Close() }()
		copyResponse(w, resp)
	})

	log.Printf("pde-argo-extension backend listening on %s operator=%s", listenAddr, operatorBase)
	log.Fatal(http.ListenAndServe(listenAddr, mux))
}

func loadRBAC() rbacConfig {
	return rbacConfig{
		writeUsers:  parseCSVSet(os.Getenv("PDE_RBAC_WRITE_USERS")),
		writeGroups: parseCSVSet(os.Getenv("PDE_RBAC_WRITE_GROUPS")),
	}
}

func parseCSVSet(raw string) map[string]struct{} {
	out := make(map[string]struct{})
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		out[part] = struct{}{}
	}
	return out
}

func (c rbacConfig) isWriter(r *http.Request) bool {
	username := strings.TrimSpace(r.Header.Get(headerArgoUsername))
	if username != "" {
		if _, ok := c.writeUsers[username]; ok {
			return true
		}
	}
	for _, group := range strings.Split(r.Header.Get(headerArgoGroups), ",") {
		group = strings.TrimSpace(group)
		if group == "" {
			continue
		}
		if _, ok := c.writeGroups[group]; ok {
			return true
		}
	}
	return false
}

func isSafeMethod(method string) bool {
	switch method {
	case http.MethodGet, http.MethodHead, http.MethodOptions:
		return true
	default:
		return false
	}
}

func envOrDefault(name string, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func copyResponse(w http.ResponseWriter, resp *http.Response) {
	for key, values := range resp.Header {
		for _, value := range values {
			w.Header().Add(key, value)
		}
	}
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}
