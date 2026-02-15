import { DonnaText } from "@/components/ui/DonnaText";

export default function Dashboard() {
    return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
            <DonnaText variant="h2" align="center" className="text-auburn">
                Welcome to your Desk.
            </DonnaText>
            <DonnaText variant="body" align="center" className="text-muted-foreground">
                Inbox processing features coming soon.
            </DonnaText>
        </div>
    );
}
