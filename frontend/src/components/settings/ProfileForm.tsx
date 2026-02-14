import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Save } from "lucide-react";
import GlassPanel from "@/components/custom/GlassPanel";
import SectionHeader from "@/components/custom/SectionHeader";
import AsyncButton from "@/components/custom/AsyncButton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProfile, useUpdateProfile } from "@/hooks/use-settings";

const profileSchema = z.object({
  full_name: z.string().min(1, "Il nome e' obbligatorio"),
  timezone: z.string().min(1, "Seleziona un fuso orario"),
  language: z.string().min(1, "Seleziona una lingua"),
});

type ProfileFormData = z.infer<typeof profileSchema>;

const timezones = [
  { value: "Europe/Rome", label: "Roma (CET/CEST)" },
  { value: "Europe/London", label: "Londra (GMT/BST)" },
  { value: "Europe/Berlin", label: "Berlino (CET/CEST)" },
  { value: "Europe/Paris", label: "Parigi (CET/CEST)" },
  { value: "America/New_York", label: "New York (EST/EDT)" },
  { value: "America/Los_Angeles", label: "Los Angeles (PST/PDT)" },
  { value: "Asia/Tokyo", label: "Tokyo (JST)" },
];

const languages = [
  { value: "it", label: "Italiano" },
  { value: "en", label: "English" },
  { value: "es", label: "Espanol" },
  { value: "fr", label: "Francais" },
  { value: "de", label: "Deutsch" },
];

export default function ProfileForm() {
  const { profile } = useProfile();
  const updateProfile = useUpdateProfile();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: "",
      timezone: "Europe/Rome",
      language: "it",
    },
  });

  useEffect(() => {
    if (profile) {
      reset({
        full_name: profile.full_name,
        timezone: profile.timezone,
        language: profile.language,
      });
    }
  }, [profile, reset]);

  const onSubmit = (data: ProfileFormData) => {
    updateProfile.mutate(data);
  };

  const timezoneValue = watch("timezone");
  const languageValue = watch("language");

  return (
    <GlassPanel>
      <SectionHeader title="Informazioni profilo" className="mb-6" />
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-lg">
        <div className="space-y-2">
          <Label htmlFor="full_name">Nome completo</Label>
          <Input
            id="full_name"
            placeholder="Il tuo nome"
            {...register("full_name")}
            aria-invalid={!!errors.full_name}
          />
          {errors.full_name && (
            <p className="text-xs text-destructive">{errors.full_name.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            value={profile?.email ?? ""}
            readOnly
            disabled
            className="opacity-60"
          />
          <p className="text-xs text-muted-foreground">
            L'email non puo' essere modificata
          </p>
        </div>

        <div className="space-y-2">
          <Label>Fuso orario</Label>
          <Select
            value={timezoneValue}
            onValueChange={(v) => setValue("timezone", v, { shouldValidate: true })}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Seleziona fuso orario" />
            </SelectTrigger>
            <SelectContent>
              {timezones.map((tz) => (
                <SelectItem key={tz.value} value={tz.value}>
                  {tz.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.timezone && (
            <p className="text-xs text-destructive">{errors.timezone.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label>Lingua</Label>
          <Select
            value={languageValue}
            onValueChange={(v) => setValue("language", v, { shouldValidate: true })}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Seleziona lingua" />
            </SelectTrigger>
            <SelectContent>
              {languages.map((lang) => (
                <SelectItem key={lang.value} value={lang.value}>
                  {lang.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.language && (
            <p className="text-xs text-destructive">{errors.language.message}</p>
          )}
        </div>

        <AsyncButton
          type="submit"
          icon={Save}
          isLoading={updateProfile.isPending}
          loadingText="Salvataggio..."
        >
          Salva modifiche
        </AsyncButton>
      </form>
    </GlassPanel>
  );
}
