"use client";

import { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import { useContactByEmail, useDiaryMutations, diaryKeys } from "@/hooks/useVault";
import { ContactCategory } from "@/services/vault";
import { useQueryClient } from "@tanstack/react-query";
import { Star, Briefcase, Globe, ShoppingCart, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ContactDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    senderEmail: string;
    senderDisplayName?: string;
}

const CATEGORIES: { key: ContactCategory; label: string; icon: typeof Star }[] = [
    { key: "vip", label: "VIP", icon: Star },
    { key: "colleague", label: "Colleague", icon: Briefcase },
    { key: "external", label: "External", icon: Globe },
    { key: "vendor", label: "Vendor", icon: ShoppingCart },
];

export function ContactDialog({ open, onOpenChange, senderEmail, senderDisplayName }: ContactDialogProps) {
    const queryClient = useQueryClient();
    const { data: existingContact, isLoading, error } = useContactByEmail(open ? senderEmail : null);
    const { createContact, updateContact } = useDiaryMutations();
    const isNew = !existingContact && !isLoading && (error || !existingContact);

    const [name, setName] = useState("");
    const [role, setRole] = useState("");
    const [organization, setOrganization] = useState("");
    const [notes, setNotes] = useState("");
    const [category, setCategory] = useState<ContactCategory | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    // Populate form when data loads
    useEffect(() => {
        if (existingContact) {
            setName(existingContact.name || "");
            setRole(existingContact.role || "");
            setOrganization(existingContact.organization || "");
            setNotes(existingContact.notes || "");
            setCategory(existingContact.category || null);
        } else if (open && !isLoading) {
            // New contact — pre-fill from sender display name
            setName(senderDisplayName || "");
            setRole("");
            setOrganization("");
            setNotes("");
            setCategory(null);
        }
    }, [existingContact, open, isLoading, senderDisplayName]);

    const handleSave = async () => {
        if (!name.trim()) return;
        setIsSaving(true);

        try {
            if (existingContact) {
                await updateContact.mutateAsync({
                    id: existingContact.id,
                    payload: {
                        name: name.trim(),
                        role: role.trim() || null,
                        organization: organization.trim() || null,
                        notes: notes.trim() || null,
                        category: category,
                    },
                });
            } else {
                await createContact.mutateAsync({
                    name: name.trim(),
                    email: senderEmail,
                    role: role.trim() || null,
                    organization: organization.trim() || null,
                    notes: notes.trim() || null,
                    category: category,
                });
            }
            queryClient.invalidateQueries({ queryKey: diaryKeys.contactLookup(senderEmail) });
            onOpenChange(false);
        } finally {
            setIsSaving(false);
        }
    };

    const initials = (name || senderEmail.split("@")[0])
        .split(" ")
        .filter(Boolean)
        .map((w) => w[0])
        .join("")
        .slice(0, 2)
        .toUpperCase();

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[420px] rounded-[14px] p-0 gap-0" overlayClassName="bg-black/40">
                <DialogHeader className="px-5 pt-5 pb-0">
                    <DialogTitle className="text-[15px] font-semibold font-inter">
                        {isNew ? "New Contact" : "Edit Contact"}
                    </DialogTitle>
                    <DialogDescription className="sr-only">
                        {isNew ? "Add a new contact" : "Edit contact details"}
                    </DialogDescription>
                </DialogHeader>

                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 size={20} className="animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className="px-5 pb-5 pt-3 space-y-4">
                        {/* Sender identity */}
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-copper/15 flex items-center justify-center text-copper text-[13px] font-bold shrink-0">
                                {initials}
                            </div>
                            <p className="text-[13px] text-muted-foreground font-inter truncate">
                                {senderEmail}
                            </p>
                        </div>

                        {/* Fields */}
                        <div className="space-y-3">
                            <input
                                placeholder="Name *"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="w-full rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary bg-transparent"
                            />
                            <div className="grid grid-cols-2 gap-3">
                                <input
                                    placeholder="Role"
                                    value={role}
                                    onChange={(e) => setRole(e.target.value)}
                                    className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary bg-transparent"
                                />
                                <input
                                    placeholder="Organization"
                                    value={organization}
                                    onChange={(e) => setOrganization(e.target.value)}
                                    className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary bg-transparent"
                                />
                            </div>
                        </div>

                        {/* Category picker */}
                        <div className="space-y-1.5">
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                Category
                            </p>
                            <div className="flex gap-2">
                                {CATEGORIES.map(({ key, label, icon: Icon }) => (
                                    <button
                                        key={key}
                                        type="button"
                                        onClick={() => setCategory(category === key ? null : key)}
                                        className={cn(
                                            "flex items-center gap-1.5 px-2.5 py-1.5 rounded-[8px] border text-[12px] font-medium font-inter transition-all",
                                            category === key
                                                ? "border-primary bg-primary/10 text-primary"
                                                : "border-border text-muted-foreground hover:border-border/70 hover:text-foreground"
                                        )}
                                    >
                                        <Icon size={12} />
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Notes */}
                        <div className="space-y-1.5">
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                Notes
                            </p>
                            <textarea
                                placeholder="e.g. preferred tone, topics to avoid, how they like to be addressed..."
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                rows={2}
                                className="w-full resize-none rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary bg-transparent"
                            />
                            <p className="text-[11px] text-muted-foreground/60 font-inter">
                                Teeks uses these notes to tailor drafts and prioritize messages from this person.
                            </p>
                        </div>

                        {/* Actions */}
                        <div className="flex justify-end gap-2 pt-1">
                            <button
                                type="button"
                                onClick={() => onOpenChange(false)}
                                className="px-3 py-1.5 rounded-[8px] text-[13px] font-medium font-inter text-muted-foreground hover:text-foreground transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleSave}
                                disabled={!name.trim() || isSaving}
                                className="px-4 py-1.5 rounded-[8px] bg-primary text-[13px] font-semibold text-white hover:bg-primary/90 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                            >
                                {isSaving ? "Saving..." : "Save"}
                            </button>
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
