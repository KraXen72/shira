export interface ServerConfig {
	final_path?: string;
	temp_path?: string;
	cookies_location?: null;
	ffmpeg_location?: string;
	itag?: string;
	cover_size?: number;
	cover_format?: string;
	cover_quality?: number;
	template_folder?: string;
	template_file?: string;
	exclude_tags?: null;
	truncate?: number;
	log_level?: string;
	save_cover?: boolean;
	overwrite?: boolean;
	print_exceptions?: boolean;
}
