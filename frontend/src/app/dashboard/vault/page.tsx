"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaCard, DonnaCardContent, DonnaCardHeader, DonnaCardTitle } from "@/components/ui/DonnaCard";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { Input } from "@/components/ui/input";
import { useVaultNotes, useVaultProposals, useVaultContacts, useVaultStats, useVaultMutations } from "@/hooks/useVault";

export default function VaultPage() {
  const [query, setQuery] = useState("");

  const notesQuery = useVaultNotes({ q: query || undefined, limit: 50 });
  const proposalsQuery = useVaultProposals("pending");
  const contactsQuery = useVaultContacts();
  const statsQuery = useVaultStats();
  const mutations = useVaultMutations();

  const loading = notesQuery.isLoading || proposalsQuery.isLoading || contactsQuery.isLoading || statsQuery.isLoading;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-auburn" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <header className="space-y-1">
        <DonnaText variant="h1" className="text-auburn">Vault</DonnaText>
        <DonnaText variant="body" className="text-muted-foreground">
          Long-lived, editable context for people, projects, decisions, and commitments.
        </DonnaText>
      </header>

      <DonnaCard>
        <DonnaCardHeader>
          <DonnaCardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
            Observability
          </DonnaCardTitle>
        </DonnaCardHeader>
        <DonnaCardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <DonnaText variant="caption" className="text-muted-foreground">Notes</DonnaText>
            <DonnaText variant="h3">{statsQuery.data?.total_notes ?? 0}</DonnaText>
          </div>
          <div>
            <DonnaText variant="caption" className="text-muted-foreground">Pending Proposals</DonnaText>
            <DonnaText variant="h3">{statsQuery.data?.proposals_pending ?? 0}</DonnaText>
          </div>
          <div>
            <DonnaText variant="caption" className="text-muted-foreground">Acceptance Rate</DonnaText>
            <DonnaText variant="h3">{Math.round((statsQuery.data?.proposal_acceptance_rate ?? 0) * 100)}%</DonnaText>
          </div>
          <div>
            <DonnaText variant="caption" className="text-muted-foreground">Context Hit Rate</DonnaText>
            <DonnaText variant="h3">{Math.round((statsQuery.data?.context_hit_rate ?? 0) * 100)}%</DonnaText>
          </div>
        </DonnaCardContent>
      </DonnaCard>

      <Tabs defaultValue="notes">
        <TabsList>
          <TabsTrigger value="notes">Notes</TabsTrigger>
          <TabsTrigger value="proposals">Proposals</TabsTrigger>
          <TabsTrigger value="contacts">Contacts</TabsTrigger>
        </TabsList>

        <TabsContent value="notes" className="space-y-4">
          <Input
            placeholder="Search vault notes..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="max-w-md"
          />
          <div className="grid md:grid-cols-2 gap-4">
            {notesQuery.data?.notes?.map((n) => (
              <DonnaCard key={n.id}>
                <DonnaCardHeader>
                  <DonnaCardTitle>{n.title}</DonnaCardTitle>
                </DonnaCardHeader>
                <DonnaCardContent>
                  <DonnaText variant="caption" className="uppercase text-muted-foreground">{n.note_type}</DonnaText>
                  <DonnaText variant="body" className="line-clamp-4 mt-2">{n.body || "No content"}</DonnaText>
                </DonnaCardContent>
              </DonnaCard>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="proposals" className="space-y-4">
          {(proposalsQuery.data?.proposals || []).map((p) => (
            <DonnaCard key={p.id}>
              <DonnaCardContent className="p-4 flex items-center justify-between gap-4">
                <div>
                  <DonnaText variant="body" className="font-medium">{p.diff_summary || p.proposal_type}</DonnaText>
                  <DonnaText variant="caption" className="text-muted-foreground">
                    {p.source_type} • confidence {Math.round((p.confidence || 0) * 100)}%
                  </DonnaText>
                </div>
                <div className="flex gap-2">
                  <DonnaButton onClick={() => mutations.approveProposal.mutate(p.id)}>Approve</DonnaButton>
                  <DonnaButton
                    variant="outline"
                    onClick={() => mutations.rejectProposal.mutate({ id: p.id, payload: { category: "not_relevant" } })}
                  >
                    Reject
                  </DonnaButton>
                </div>
              </DonnaCardContent>
            </DonnaCard>
          ))}
        </TabsContent>

        <TabsContent value="contacts" className="space-y-4">
          {(contactsQuery.data?.contacts || []).map((c) => (
            <DonnaCard key={c.email}>
              <DonnaCardContent className="p-4 flex items-center justify-between">
                <div>
                  <DonnaText variant="body" className="font-medium">{c.name || c.email}</DonnaText>
                  <DonnaText variant="caption" className="text-muted-foreground">{c.email} • {c.message_count} msgs</DonnaText>
                </div>
                <DonnaButton onClick={() => mutations.promoteContact.mutate({ email: c.email, display_name: c.name })}>
                  Promote
                </DonnaButton>
              </DonnaCardContent>
            </DonnaCard>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}

