"use client";

import { useSettings } from "@/hooks/useSettings";
import { useAuth } from "@/context/AuthContext";
import { DonnaCard, DonnaCardContent, DonnaCardHeader, DonnaCardTitle } from "@/components/ui/DonnaCard";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { SettingRow } from "@/components/ui/SettingRow";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Switch } from "@/components/ui/Switch";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { User, Settings as SettingsIcon, Shield, Lock, Download, Mail, Trash2, LogOut, Loader2, Monitor, AlertTriangle } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useState, useEffect } from "react";
import { supabase } from "@/utils/supabase/client";
import { exportUserData, revokeGmailAccess, deleteAllData } from "@/services/privacy";
import { toast } from "sonner"; // Assuming toast is available or I can add it

export default function SettingsPage() {
    const { user, signOut } = useAuth();
    const { settings, isLoading, updateSetting, isUpdating } = useSettings();
    const [instructions, setInstructions] = useState('');
    const [isDeleteOpen, setIsDeleteOpen] = useState(false);

    useEffect(() => {
        if (settings?.task_detection_instructions !== undefined) {
            setInstructions(settings.task_detection_instructions || '');
        }
    }, [settings?.task_detection_instructions]);

    const handleSaveInstructions = () => {
        if (instructions !== settings?.task_detection_instructions) {
            updateSetting('task_detection_instructions', instructions || null);
            toast.success("Instructions updated");
        }
    };

    const handleSignOutAll = async () => {
        try {
            const { error } = await supabase.auth.signOut({ scope: 'global' });
            if (error) throw error;
            toast.success("Signed out from all devices");
            window.location.href = '/login';
        } catch (error) {
            toast.error("Failed to sign out from all devices");
        }
    };

    const handleExport = async () => {
        try {
            const data = await exportUserData();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `teeks_export_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            toast.success("Data export started");
        } catch (error) {
            toast.error("Failed to export data");
        }
    };

    const handleDeleteAccount = async () => {
        try {
            await deleteAllData();
            toast.success("Account deleted successfully");
            await supabase.auth.signOut();
            window.location.href = '/login';
        } catch (error) {
            toast.error("Failed to delete account. Please try again.");
            setIsDeleteOpen(false);
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <header className="space-y-1 px-1">
                <DonnaText variant="h1" className="text-auburn">Settings</DonnaText>
                <DonnaText variant="body" className="text-muted-foreground">
                    Manage your command center and AI assistant.
                </DonnaText>
            </header>

            <Tabs defaultValue="general" className="w-full">
                <TabsList className="bg-transparent border-b border-border w-full justify-start rounded-none h-auto p-0 gap-8">
                    <TabsTrigger value="general" className="rounded-none border-b-2 border-transparent data-[state=active]:border-auburn data-[state=active]:bg-transparent data-[state=active]:text-foreground bg-transparent px-1 pb-4">
                        General
                    </TabsTrigger>
                    <TabsTrigger value="profile" className="rounded-none border-b-2 border-transparent data-[state=active]:border-auburn data-[state=active]:bg-transparent data-[state=active]:text-foreground bg-transparent px-1 pb-4">
                        Profile
                    </TabsTrigger>
                    <TabsTrigger value="security" className="rounded-none border-b-2 border-transparent data-[state=active]:border-auburn data-[state=active]:bg-transparent data-[state=active]:text-foreground bg-transparent px-1 pb-4">
                        Security
                    </TabsTrigger>
                    <TabsTrigger value="privacy" className="rounded-none border-b-2 border-transparent data-[state=active]:border-auburn data-[state=active]:bg-transparent data-[state=active]:text-foreground bg-transparent px-1 pb-4">
                        Privacy
                    </TabsTrigger>
                </TabsList>

                {/* General Settings */}
                <TabsContent value="general" className="mt-6 space-y-6">
                    <DonnaCard>
                        <DonnaCardHeader>
                            <DonnaCardTitle className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
                                AI & Automation
                            </DonnaCardTitle>
                        </DonnaCardHeader>
                        <DonnaCardContent className="p-0">
                            <SettingRow
                                icon={<SettingsIcon />}
                                title="Auto-Approve Tasks"
                                subtitle="Automatically add AI-detected tasks to your list"
                                rightElement={
                                    <Switch
                                        checked={settings?.auto_approve_tasks ?? false}
                                        onCheckedChange={(val) => updateSetting('auto_approve_tasks', val)}
                                    />
                                }
                            />
                            <SettingRow
                                icon={<Mail />}
                                title="Quick Reply from Task"
                                subtitle="Enable AI-drafted replies directly from tasks"
                                rightElement={
                                    <Switch
                                        checked={settings?.enable_quick_reply_from_task ?? false}
                                        onCheckedChange={(val) => updateSetting('enable_quick_reply_from_task', val)}
                                    />
                                }
                            />
                        </DonnaCardContent>
                    </DonnaCard>

                    <DonnaCard>
                        <DonnaCardHeader>
                            <DonnaCardTitle className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
                                Detection Instructions
                            </DonnaCardTitle>
                        </DonnaCardHeader>
                        <DonnaCardContent className="space-y-4">
                            <DonnaText variant="caption" className="text-muted-foreground">
                                Guide {settings?.assistant_name || 'Teeks'} on how to identify tasks in your emails. Mention specific keywords, projects, or contexts to watch for.
                            </DonnaText>
                            <Textarea
                                placeholder="e.g. Focus on requests from the executive team..."
                                value={instructions}
                                onChange={(e) => setInstructions(e.target.value)}
                                onBlur={handleSaveInstructions}
                                className="min-h-[120px] bg-linen/30 border-auburn/10 focus:border-auburn/30 transition-all"
                            />
                            {isUpdating && <DonnaText variant="caption" className="text-auburn animate-pulse">Saving changes...</DonnaText>}
                        </DonnaCardContent>
                    </DonnaCard>
                </TabsContent>

                {/* Profile Settings */}
                <TabsContent value="profile" className="mt-6 space-y-6">
                    <DonnaCard>
                        <div className="p-8 flex flex-col items-center text-center space-y-4 border-b border-border/40">
                            <div className="w-24 h-24 rounded-full bg-accent-precision flex items-center justify-center text-white text-3xl font-serif">
                                {user?.email?.[0].toUpperCase() || 'U'}
                            </div>
                            <div className="space-y-1">
                                <DonnaText variant="h2">{user?.email}</DonnaText>
                                <DonnaText variant="body" className="text-muted-foreground">
                                    {settings?.subscription_tier === 'pro' ? 'Pro Member' : 'Free Trial'}
                                </DonnaText>
                            </div>
                        </div>
                        <DonnaCardContent className="p-0" />
                    </DonnaCard>
                </TabsContent>

                {/* Security Settings */}
                <TabsContent value="security" className="mt-6 space-y-6">
                    <DonnaCard>
                        <DonnaCardHeader>
                            <DonnaCardTitle className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
                                Active Sessions
                            </DonnaCardTitle>
                        </DonnaCardHeader>
                        <DonnaCardContent className="p-0">
                            <div className="p-4 flex items-center justify-between border-b border-border/40 bg-accent/20">
                                <div className="flex items-center gap-4">
                                    <div className="w-9 h-9 rounded-lg bg-success/20 flex items-center justify-center">
                                        <Monitor className="text-success" size={20} />
                                    </div>
                                    <div>
                                        <DonnaText className="font-medium">Current Session</DonnaText>
                                        <DonnaText variant="caption" className="text-muted-foreground">
                                            This device • Active now
                                        </DonnaText>
                                    </div>
                                </div>
                                <div className="px-2 py-0.5 rounded bg-success/10 text-success text-[10px] uppercase font-bold tracking-tighter">
                                    Current
                                </div>
                            </div>
                            <SettingRow
                                icon={<Lock />}
                                iconColor="#7E2E2E"
                                title="Sign Out from All Devices"
                                subtitle="Log out of all other active sessions for security"
                                onClick={handleSignOutAll}
                                destructive
                            />
                        </DonnaCardContent>
                    </DonnaCard>
                </TabsContent>

                {/* Privacy Settings */}
                <TabsContent value="privacy" className="mt-6 space-y-6">
                    <DonnaCard>
                        <DonnaCardHeader>
                            <DonnaCardTitle className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
                                Data Management
                            </DonnaCardTitle>
                        </DonnaCardHeader>
                        <DonnaCardContent className="p-0">
                            <SettingRow
                                icon={<Download />}
                                title="Export My Data"
                                subtitle="Download a complete copy of your data (JSON)"
                                onClick={handleExport}
                            />
                            <SettingRow
                                icon={<Shield />}
                                title="Revoke Gmail Access"
                                subtitle="Disconnect your Google account and delete synced data"
                                onClick={() => revokeGmailAccess().then(() => toast.success("Access revoked")).catch(() => toast.error("Failed to revoke access"))}
                                destructive
                            />
                        </DonnaCardContent>
                    </DonnaCard>

                    <div className="p-4 rounded-lg border border-destructive/20 bg-destructive/5 space-y-4">
                        <div className="space-y-1">
                            <DonnaText className="font-bold text-destructive flex items-center gap-2">
                                <Trash2 size={16} /> Danger Zone
                            </DonnaText>
                            <DonnaText variant="caption" className="text-destructive/80">
                                Deleting your account will permanently remove all your data, including settings, tasks, and memory. This action is irreversible.
                            </DonnaText>
                        </div>
                        <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
                            <DialogTrigger asChild>
                                <DonnaButton variant="outline" className="border-destructive text-destructive hover:bg-destructive hover:text-white">
                                    Delete My Account
                                </DonnaButton>
                            </DialogTrigger>
                            <DialogContent className="border-destructive/20 bg-linen">
                                <DialogHeader>
                                    <DialogTitle className="text-destructive flex items-center gap-2">
                                        <AlertTriangle size={20} />
                                        Delete Account Permanently?
                                    </DialogTitle>
                                    <DialogDescription className="text-muted-foreground pt-4">
                                        This action cannot be undone. This will permanently delete your account and remove your data from our servers, including:
                                        <ul className="list-disc pl-5 mt-2 space-y-1">
                                            <li>All tasks and emails</li>
                                            <li>Personalized AI memory</li>
                                            <li>Settings and preferences</li>
                                        </ul>
                                    </DialogDescription>
                                </DialogHeader>
                                <DialogFooter className="mt-6 flex gap-2">
                                    <DonnaButton variant="ghost" onClick={() => setIsDeleteOpen(false)}>
                                        Cancel
                                    </DonnaButton>
                                    <DonnaButton
                                        variant="default"
                                        className="bg-destructive hover:bg-destructive/90 text-white"
                                        onClick={handleDeleteAccount}
                                    >
                                        Yes, Delete Everything
                                    </DonnaButton>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    );
}
